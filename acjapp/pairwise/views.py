# Drawing Test - Django-based comparative judgement for art assessment
# Copyright (C) 2021  Steve and Ray Heil

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from django.shortcuts import render, redirect, get_object_or_404
from datetime import datetime
from django.http import HttpResponse
from .models import Item, Comparison, Set, WinForm
from .utils import * 
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm

def index(request):
    if request.user.is_authenticated:
        userid=request.user.id
        allowed_sets_ids = get_allowed_sets(userid)
        request.session['sets'] = allowed_sets_ids
    return render(request, 'pairwise/index.html', {})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if 'next' in request.POST:
                return redirect(request.POST.get('next'))
            else:
                return redirect('index.html')
    else:
        form = AuthenticationForm()
    return render(request,'pairwise/login.html', {'form': form })

def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('index.html')

@login_required(login_url="login")
def item_detail(request, pk):
    item=get_object_or_404(Item, pk=pk)
    return render(request, 'pairwise/item_detail.html', {'item': item})

@login_required(login_url="login")
def stats(request, set):
    judgelist = [] # the make_groups function can also take preselected judges when needed -- right now command line only
    j, a, corrstats_df, corr_chart_data = make_groups(set, judgelist)
    if len(j) < 2:
        judges = [request.user.id]
        a2 = 1
        corrstats = None
    else:
        judges = j
        a2 = a
        corrstats = corrstats_df.to_html()
    computed_items = get_computed_items(set, judges)

    #build lists to send to Highchart charts for error bar chart -- resort for low to high scores
    lohi_computed_items = sorted(computed_items, key = lambda x: x.probability)
    itemids=[]
    fisher=[]
    scores=[]
    scoreerrors=[]
    for item in lohi_computed_items:
        if item.ep == None:
            pass
        else: 
            itemids.append(item.idcode)
            fisher.append(item.fisher_info)
            scores.append(item.ep)
            scoreerrors.append([item.lo95ci, item.hi95ci])

    return render(request, 'pairwise/stats.html', {
        'item_table': computed_items, 
        'set': set,
        'judges': judges,
        'a': a2,
        'corrstats': corrstats,
        'corr_chart_data': corr_chart_data,
        'itemids': itemids,
        'fisher': fisher,
        'scores': scores,
        'scoreerrors': scoreerrors
        } 
    )

@login_required(login_url="login")
def set_view(request, pk):
    judges = []
    judges.append(request.user.id)
    allowed_sets_ids = get_allowed_sets(request.user.id)
    request.session['sets'] = allowed_sets_ids
    computed_items = get_computed_items(pk, judges)
    computed_items.sort(key = lambda x: x.probability, reverse=True)
    return render(request, 'pairwise/set.html', {
        'pk': pk, 
        'set_items': computed_items
        }
    )

@login_required(login_url="login")
def comparisons(request, set):
    userid=request.user.id
    allowed_sets_ids = get_allowed_sets(userid)
    request.session['sets']= allowed_sets_ids
    if int(set) not in allowed_sets_ids:    
        html="<p>ERROR: Set not available.</p>"
        return HttpResponse(html)
    comparisons = Comparison.objects.filter(set=set, judge=userid)
    return render(request, 'pairwise/comparison_list.html', {
        'set': set,
        'comparisons': comparisons,
        }
    )
       
@login_required(login_url="login")
def compare(request, set):
    userid=request.user.id
    allowed_sets_ids = get_allowed_sets(userid)
    request.session['sets']= allowed_sets_ids
    message = "" # empty message will be ignored in template
    if int(set) not in allowed_sets_ids:    
        html = "<p>ERROR: Set not available.</p>"
        return HttpResponse(html) 
    if request.method == 'POST': #if arriving here after submitting a form
        winform = WinForm(request.POST)
        if winform.is_valid():
            comparison = winform.save(commit=False)
            comparison.judge = request.user
            comparison.itemi = Item.objects.get(pk=request.POST.get('itemi'))
            comparison.itemj = Item.objects.get(pk=request.POST.get('itemj'))
            comparison.set = Set.objects.get(pk=set)
            start = comparison.form_start_variable # still a float from form
            starttime = datetime.fromtimestamp(start) # convert back to datetime
            end = datetime.now() # use datetime instead of timezone
            comparison.decision_end = end
            comparison.decision_start = starttime
            duration = end - starttime
            comparison.duration = duration
            
            # make sure page refresh doesn't duplicate a comparison
            try:
                last_comp_by_user = Comparison.objects.filter(judge=request.user).latest('pk')
            except:
                last_comp_by_user = None #note: this may not be necessary if query automatically gives us none
                comparison.save()
            if last_comp_by_user:
                if (comparison.itemi == last_comp_by_user.itemi) and (comparison.itemj == last_comp_by_user.itemj) and (comparison.judge == last_comp_by_user.judge):        
                    message = "No comparison saved."
                else:
                    comparison.save()      
                    message = "Comparison saved."
  
    #whether POST or GET, set all these variables afresh and render comparision form template        
    compslist, itemi, itemj, j_list = item_selection(set, userid)
    compscount = len(compslist)
    item_count = Item.objects.filter(set=set).count()
    compsmax = int(item_count * (item_count - 1) * .5)
    now = datetime.now()
    starttime = now.timestamp
    set_object = Set.objects.get(pk=set)
    if set_object.override_end == None: # check if an comparisons limit override has been defined for the set
        compstarget = int(round((.66 * compsmax),-1))
    else:
        compstarget = set_object.override_end
    winform = WinForm()
    if len(j_list) == 0 or compscount >= compstarget:
        itemi=None
        itemj=None
    return render(request, 'pairwise/compare.html', {
            'itemi': itemi,
            'itemj': itemj,
            'winform': winform,
            'set': set,
            'starttime': starttime,
            'j_list': j_list,
            'allowed_sets_ids': allowed_sets_ids,
            'compscount': compscount,
            'compsmax': compsmax,
            'compstarget': compstarget,
            'set_object': set_object,
            'message': message
            } 
        )