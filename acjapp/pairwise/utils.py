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

from .models import Script, Comparison, Set
import numpy as np
from numpy import log, sqrt
import random
import itertools
from operator import itemgetter
from chartit import DataPool, Chart
import pandas
import re
import csv
from scipy.stats import spearmanr, percentileofscore

class ComputedScript:
    def __init__(self, id, idcode, idcode_f, comps, wins, logit, probability, stdev, fisher_info, se, ep, lo95ci, hi95ci, samep, rank, randomsorter, percentile):
            self.id = id
            self.idcode = idcode
            self.idcode_f = idcode_f
            self.comps = int(comps)
            self.wins = wins
            self.logit = logit
            self.probability = probability
            self.stdev = stdev
            self.fisher_info = fisher_info
            self.se = se
            self.ep = ep
            self.lo95ci = lo95ci
            self.hi95ci = hi95ci
            self.samep = samep 
            self.rank = rank 
            self.randomsorter = randomsorter
            self.percentile = percentile

def get_allowed_sets(userid):
    sets = Set.objects.filter(judges__id__exact=userid).order_by('pk')
    allowed_sets_ids = []
    for set in sets:
        allowed_sets_ids.append(set.id)
    return allowed_sets_ids

def script_selection(set, userid):
    scriptcount = Script.objects.filter(set=set).count()
    set_object = Set.objects.get(pk=set) # sometimes we need to object not just the string of the set number
    compslist = build_compslist(set, userid)
    judges = [userid] #judges must be a list, even if it only has one judge in it
    computed_scripts_for_user_in_set = get_computed_scripts(set, judges) 
    maxcomps=(scriptcount * (scriptcount-1)/2)
    switch=min(scriptcount + (scriptcount * (scriptcount-1)/6), maxcomps)
    if len(compslist) < switch: #prioritize minimum comps until comps = min of n+max/3 or max, then . . . 
        computed_scripts_for_user_in_set.sort(key = lambda x: (x.comps, x.samep, x.fisher_info, x.randomsorter)) 
    else: #prioritize lowest same probability (least distinct estimate <-1, samep = -1 indicates unique estimate)
        computed_scripts_for_user_in_set.sort(key = lambda x: (x.samep, x.comps, x.fisher_info, x.randomsorter))
        if computed_scripts_for_user_in_set[0].samep == -1 and set_object.override_end == None:
            return compslist, None, None, [] # everything is empty

    # Go through all comparable scripts, and choose the first as scripti. 
    # Then calculate the difference in probability 'p_diff' between scripti and every other script
    j_list = []
    for i, script in enumerate(computed_scripts_for_user_in_set):
        if i == 0:
            if script.comps == scriptcount-1:
                return compslist, None, None, [] # everything is empty
            scripti = Script.objects.get(pk = script.id)
            p_i = float(script.probability)
        elif [scripti.id, script.id] not in compslist and [script.id, scripti.id] not in compslist: # don't consider this scriptj if it's already been compared
            p_j = float(script.probability)
            p_diff = round(abs(p_i - p_j),3)
            j_list.append([script.id, p_diff, script.comps, script.samep, script.fisher_info, script.randomsorter])
    
    # Based on lowest probability difference, then random index, choose the most similar script to display as scriptj
    if j_list: 
        j_list.sort(key=itemgetter(1,5)) # 1 is p_diff, 5 is randomsorter
        scriptj = Script.objects.get(pk = j_list[0][0]) # the item that has the smallest log odds difference (lodiff)
    else: # if there are no possibilities, we can't choose a scriptj at all. whatever recieves the request will have to deal with a NoneType
        j_list = []
        scriptj = None
    return compslist, scripti, scriptj, j_list

def get_computed_scripts(set, judges):
    computed_scripts_for_user_in_set =[]
    scripts = Script.objects.filter(set=set)
    for script in scripts:
        comps, wins = compute_comps_wins(script, judges)
        logit, probability, stdev, fisher_info, se, ep, hi95ci, lo95ci, randomsorter = compute_more(comps, wins)
        computed_scripts_for_user_in_set.append(
            ComputedScript(
                script.id,
                script.idcode, 
                script.idcode_f, 
                comps, 
                wins, 
                logit, 
                '{:.3f}'.format(probability), 
                '{:.2f}'.format(stdev), 
                round(fisher_info,2), 
                se, 
                ep, 
                lo95ci, 
                hi95ci, 
                0, # samep
                0, # rank
                randomsorter,
                0, #percentile
                )
        )  
    computed_scripts_for_user_in_set = set_ranks(computed_scripts_for_user_in_set)
    #computed_scripts_for_user_in_set = set_percentiles(computed_scripts_for_user_in_set)
    return computed_scripts_for_user_in_set

def build_compslist(set, userid):
    comps = Comparison.objects.filter(set=set).filter(judge=userid)
    compslist = []
    for comp in comps:
        i = comp.scripti.id
        j = comp.scriptj.id 
        compslist.append([i, j])
    return compslist

def compute_comps_wins(script, judges):
    comps = .001
    wins = 0
    for judge in judges:
        #count all the comparisons each script has been involved in for user
        comparisons_as_i_for_judge_count = Comparison.objects.filter(scripti=script, judge__pk=judge).count()
        comparisons_as_j_for_judge_count = Comparison.objects.filter(scriptj=script, judge__pk=judge).count()
        thisjudgecomps = comparisons_as_i_for_judge_count + comparisons_as_j_for_judge_count

        #count all the comparisons this script has won
        wins_as_i_for_judge_count = Comparison.objects.filter(wini=1, scripti=script, judge__pk=judge).count()
        wins_as_j_for_judge_count = Comparison.objects.filter(wini=0, scriptj=script, judge__pk=judge).count()
        thisjudgewins = wins_as_i_for_judge_count + wins_as_j_for_judge_count
    
        comps += thisjudgecomps 
        wins += thisjudgewins
    return comps, wins

def compute_more(comps, wins):
    #compute probability of winning for each script based on comparisons so far
    probability = wins/(comps) # comps comes in with a .001 so no error dividing by 0
    #probability = (wins + .5)/(comps + 1) # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 23
    #compute the standard deviation of sample and standard error of sample mean 
    stdev = sqrt(((((1 - probability) ** 2) * wins) + (((0 - probability) ** 2) * (int(comps) - wins))) / (comps + .001))
    #compute if not all wins or all losses so far
    if (round(probability,3) == 1) or (probability <= 0):
        logit = None
        fisher_info = 0
        se = None
        ep = None
        hi95ci = None
        lo95ci = None
        percentile = None
    else: 
        fisher_info = 1/(probability * (1 - probability)) # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 20
        se = round(stdev / sqrt(comps),3) # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 19
        loglikelihood = (wins * log(probability)) + (comps-wins) * log(1-probability) # not using this directly
        logit = round(log(probability/(1 - probability)),3) 
        fisher_info_of_logit = comps * probability * ( 1 - probability) # se http://personal.psu.edu/abs12//stat504/online/01b_loglike/10_loglike_alternat.htm        
        ci = 1.96 * sqrt(1/fisher_info_of_logit) # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 30
        b = 10 # determine the spread of parameter values
        a = int(100 - (3.18 * b )) # aim for high parameter of 100 for probability .96 / logit of 3.18
        ep = round((logit * b), 1) + a
        hi95ci = round(((logit + ci) * b), 1) + a
        lo95ci = round(((logit - ci) * b), 1) + a

    randomsorter = random.randint(0,1000)
    return logit, probability, stdev, fisher_info, se, ep, hi95ci, lo95ci, randomsorter
    # more here: http://personal.psu.edu/abs12//stat504/online/01b_loglike/01b_loglike_print.htm

def set_ranks(computed_scripts_for_user_in_set):
    #now decrease (for sorting later) samep by one for every script including self with matching probability and set a rank value fo each
    computed_scripts_for_user_in_set.sort(key = lambda x: x.probability, reverse=True)
    rank=0
    for script in computed_scripts_for_user_in_set:
        for match in computed_scripts_for_user_in_set:
            if match.probability == script.probability:
                match.samep -= 1
        if script.samep == -1: #if there's only one at that value, then increase rank increment 1 for next 
            rank += 1
        script.rank=rank
    return computed_scripts_for_user_in_set

def set_percentiles(computed_scripts_for_user_in_set):
    scores = []
    for script in computed_scripts_for_user_in_set:
        try: 
            scores.extend(script.probability)
            print(script.probability)
        except:
            scores.extend(None)
    for script in computed_scripts_for_user_in_set:
        print(script.percentile)
        script.percentile=percentileofscore(scores, script.logit, kind='rank')
    print(scores)
    return computed_scripts_for_user_in_set


def corr_matrix(setid):
    set_judge_script_rank = {}
    set_judge_script_estimate = {}
    set = Set.objects.get(pk=setid)
    for judge in set.judges.all():
        computed_scripts = get_computed_scripts(set, [judge.id])
        computed_scripts.sort(key = lambda x: x.id)
        set_judge_script_rank[judge.id]=[]
        set_judge_script_estimate[judge.id]=[]
        for script in computed_scripts:
            set_judge_script_rank[judge.id].append(script.rank)
            set_judge_script_estimate[judge.id].append(script.logit)
    rankdf = pandas.DataFrame(data = set_judge_script_rank)
    estdf = pandas.DataFrame(data = set_judge_script_estimate)
    k = rankdf.corr('kendall')
    s = rankdf.corr('spearman')
    p = estdf.corr('pearson')
    return s, k, p

def make_groups_rho(setid):
    setobject=Set.objects.get(pk=setid)
    try: # if comps exist for this set, query a list of unique judge ids who have made comparisons on this set
        judgelist = Comparison.objects.filter(set=setobject).values_list('judge_id', flat=True).distinct()
    except:
        judgelist = None
    if len(judgelist) < 2:
        bestgroup = []
        bestagreement = 0
        stats_df = None
        return bestgroup, bestagreement, stats_df
    set_judge_script_rank = {}
    for judge in judgelist:
        computed_scripts = get_computed_scripts(setobject, [judge])
        computed_scripts.sort(key = lambda x: x.id)
        set_judge_script_rank[judge]=[]
        for script in computed_scripts:
            set_judge_script_rank[judge].append(script.rank)
    if len(judgelist) == 2:
        coef, p = spearmanr(set_judge_script_rank[0],set_judge_script_rank[1])
        bestgroup = judgelist
        bestagreement = coef
        stats_df = pandas.DataFrame(set_judge_script_rank)
        return bestgroup, bestagreement, stats_df
    else:
        judgepairs = itertools.combinations(judgelist, 2)
        judgepaircorr = {}
        for judgepair in judgepairs:
            judge1 = judgepair[0]
            judge2 = judgepair[1]
            coef, p = spearmanr(set_judge_script_rank[judge1], set_judge_script_rank[judge2])
            judgepaircorr[judgepair]=[coef, p]
        judgegroups = itertools.combinations(judgelist, 3)
        corrdata = []
        for judgegroup in judgegroups:
            judge1=judgegroup[0]
            judge2=judgegroup[1] 
            judge3=judgegroup[2]  
            rho1 = judgepaircorr[(judge1,judge2)][0]
            p1 = judgepaircorr[(judge1,judge2)][1]
            rho2 = judgepaircorr[(judge1,judge3)][0]
            p2 = judgepaircorr[(judge1,judge3)][1]
            rho3 = judgepaircorr[(judge2,judge3)][0]
            p3 = judgepaircorr[(judge2,judge3)][1]
            rho_list = [rho1, rho2, rho3]
            rho_average = np.mean(rho_list)
            data = [
                (judge1,judge2,judge3), 
                rho_average, 
                (judge1,judge2),
                rho1,
                p1,
                (judge1,judge3),
                rho2,
                p2,
                (judge2,judge3),
                rho3,
                p3,
            ]
            corrdata.append(data)
    df = pandas.DataFrame(corrdata, columns = ['Judge Group', 'Rho Average','Pair 1 Judges', 'Pair 1 Rho','Pair 1 P-value', 'Pair 2 Judges', 'Pair 2 Rho', 'Pair 2 P-value', 'Pair 3 Judges', 'Pair 3 Rho', 'Pair 3 P-value'])
    df_sorted = df.sort_values(by='Rho Average', ascending=False)
    stats_df = df_sorted.set_index('Judge Group')
    b = stats_df.iat[0, 0]
    bestagreement = round(b,3)
    bestgroup = pandas.DataFrame.first_valid_index(stats_df)
    return bestgroup, bestagreement, stats_df

# this function not currently in use. Selects 3 judges with top percent agreement when there are more than three
# when there are 0, 1, or 2 judges with comparisons for the given set it returns workable empties
# interrater percent agreement reference: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3900052/
def make_groups_percentagree(setobject):
    try: # if comps exist for this set, query a list of unique judge ids who have made comparisons on this set
        judgelist = Comparison.objects.filter(set=setobject).values_list('judge_id', flat=True).distinct()
    except:
        judgelist = None
    if len(judgelist) < 2:
        bestgroup = []
        bestagreement = 0
        stats_df = None
        return bestgroup, bestagreement, stats_df

    #create scriptpairs from combinations of all scripts in set
    
    scripts = Script.objects.filter(set=setobject)
    scriptlist = []
    for script in scripts:
        scriptlist.append(script.id)
    judgecomps = {}
    # for each scriptpair add to the list of comparision judgments made by each judge-- 
    for judge in judgelist: # first iterate through all judges so you can update judge's list of comps
        column =[]
        scriptpairs = itertools.combinations(scriptlist, 2)
        for scriptpair in scriptpairs:        
            try: # get a comparison that matches that scriptpair order left and right if it exists for this judge
                comp = Comparison.objects.get(set = setobject, judge = judge, scripti__id = scriptpair[0], scriptj__id = scriptpair[1])
                row = [comp.scripti.id, comp.scriptj.id, comp.wini] 
            except:
                try: # get a comparison that matches reverse order of script pair if there is one for this judge
                    comp = Comparison.objects.get(set = setobject, judge = judge, scriptj__id = scriptpair[0], scripti__id = scriptpair[1] )
                    row = [comp.scriptj.id, comp.scripti.id]
                    if comp.wini == 1:
                        row.extend([0])
                    else:
                        row.extend([1])
                except:
                    #this judge has no matching comp in either order
                    comp = None
                    row = ([None, None, None])
            column.append(row)
        judgecomps.update({str(judge): column}) # update the dict to include the whole column
        # where each row in the column contains [scriptid, scriptid, win]

    if len(judgelist) > 2:
        combo_n = 3
    else:
        combo_n = 2
    judgegroups = itertools.combinations(judgelist, combo_n)
    judgegroupagreement = {} 
    judgegroupstats = {}
    judges=[]
    x=[]
    n=[]
    p=[]
    se=[]
    # calculate percent agreement among judges in each group
    for judgegroup in judgegroups:
        column = []
        for row in judgecomps[str(judgegroup[0])]:
            #row for first judge's list of comparisions
            flag = 0 # using this flag variable to signal any missing pair in another judge's comps
            
            if row == [None, None, None]: 
                # don't look for matching comps if the this pair hasn't been compared yet
                pass # skip this row and don't add it to the column
            else:
                #setting row_opp to the opposite decision is a clumsy way to set up to make sure the pair doesn't show up at all in other judges' comps
                if row[2] == 1:
                    row_opp = [row[0],row[1],0]
                else:
                    row_opp = [row[0],row[1],1]

                rowtally = 1 # judge agrees with self, next how about others?                
                
                if row in judgecomps[str(judgegroup[1])]:
                    rowtally += 1 # add one agreement for the second judge  
                elif row_opp not in judgecomps[str(judgegroup[1])]:
                    flag += 1 #the pair is not in second judge's list at all and signal not to add this row to the column    
                if combo_n > 2:
                    if row in judgecomps[str(judgegroup[2])]:  
                        rowtally += 1   # if there is a third judge, add one agreement for the third
                    elif row_opp not in judgecomps[str(judgegroup[2])]:
                        flag += 1 #the pair is not in the third judge's list at all and increase signal not to add this row to the column
                if flag == 0:
                    column.append(int(rowtally/combo_n)) #added Int() so it only counts 1 if all three agree, and only 0 if all three share that pair 
        judgegroupagreement.update({str(judgegroup): column})

        # calculating stats for each row and appending to list for later dictionary & dataframe 
        rowx=sum(judgegroupagreement[str(judgegroup)])
        rown=len(judgegroupagreement[str(judgegroup)])
        maxcomps = (len(scriptlist)*(len(scriptlist)-1))/2
        if rown * 20 > maxcomps: # only if n of shared comparisons > 1/20 possible comparisons
            judges.append(judgegroup) # judges is a key of the dictionary, adding to its values list
            x.append(rowx) # x will be a key, adding to values list
            n.append(rown) # n will be a key, adding to values list
            p.append(rowx/rown) # p will be a key, adding to values list
            std=np.std(judgegroupagreement[str(judgegroup)])
            se.append(std/sqrt(rown)) # se will be a key, adding to values list
        
    judgegroupstats.update({'judges': judges, "p": p,"se": se, "x": x, "n": n}) # finally, the dict. to build with keys and value lists
    
    df = pandas.DataFrame(judgegroupstats) # make a dataframe to pass to the template
    stats_df_indexkey=df.sort_values(by='p', ascending = False) # sort by p highest to lowest
    stats_df=stats_df_indexkey.set_index('judges')
    bestgroupstring = str(stats_df.index[0]) # choose first judgegroup string
    bestgroupids = re.findall('[0-9]+', bestgroupstring) # extract the numeric ids from string
    b = stats_df.iat[0, 0]
    bestagreement = round(b *100, 1)
    bestgroup = []
    for id in bestgroupids:
        bestgroup.append(int(id)) # turn the id strings into integers
    return bestgroup, bestagreement, stats_df

#added this function for command-line, just like make_groups above but takes judgelist as input, skips selecting best group. Needs to be consolidated into above function                
def group_stats(setobject, judgelist):
    if len(judgelist) < 2:
        bestgroup = []
        bestagreement = 0
        stats_df = None
        return bestgroup, bestagreement, stats_df
    #create scriptpairs from combinations of all scripts in set
    scripts = Script.objects.filter(set=setobject)
    scriptlist = []
    for script in scripts:
        scriptlist.append(script.id)
    judgecomps = {}
    # for each scriptpair add to the list of comparision judgments made by each judge-- 
    for judge in judgelist: # first iterate through all judges so you can update judge's list of comps
        column =[]
        scriptpairs = itertools.combinations(scriptlist, 2)
        for scriptpair in scriptpairs:        
            try: # get a comparison that matches that scriptpair order left and right if it exists for this judge
                comp = Comparison.objects.get(set = setobject, judge = judge, scripti__id = scriptpair[0], scriptj__id = scriptpair[1])
                row = [comp.scripti.id, comp.scriptj.id, comp.wini] 
            except:
                try: # get a comparison that matches reverse order of script pair if there is one for this judge
                    comp = Comparison.objects.get(set = setobject, judge = judge, scriptj__id = scriptpair[0], scripti__id = scriptpair[1] )
                    row = [comp.scriptj.id, comp.scripti.id]
                    if comp.wini == 1:
                        row.extend([0])
                    else:
                        row.extend([1])
                except:
                    #this judge has no matching comp in either order
                    comp = None
                    row = ([None, None, None])
            column.append(row)
        judgecomps.update({str(judge): column}) # update the dict to include the whole column
        # where each row in the column contains [scriptid, scriptid, win]
    if len(judgelist) > 2:
        combo_n = 3
    else:
        combo_n = 2
    judgegroups = itertools.combinations(judgelist, combo_n)
    judgegroupagreement = {} 
    judgegroupstats = {}
    judges=[]
    x=[]
    n=[]
    p=[]
    se=[]
    # calculate percent agreement among judges in each group
    for judgegroup in judgegroups:
        column = []
        for row in judgecomps[str(judgegroup[0])]:
            #row for first judge's list of comparisions
            flag = 0 # using this flag variable to signal any missing pair in another judge's comps
            
            if row == [None, None, None]: 
                # don't look for matching comps if the this pair hasn't been compared yet
                pass # skip this row and don't add it to the column
            else:
                #setting row_opp to the opposite decision is a clumsy way to set up to make sure the pair doesn't show up at all in other judges' comps
                if row[2] == 1:
                    row_opp = [row[0],row[1],0]
                else:
                    row_opp = [row[0],row[1],1]

                rowtally = 1 # judge agrees with self, next how about others?                
                
                if row in judgecomps[str(judgegroup[1])]:
                    rowtally += 1 # add one agreement for the second judge  
                elif row_opp not in judgecomps[str(judgegroup[1])]:
                    flag += 1 #the pair is not in second judge's list at all and signal not to add this row to the column    
                if combo_n > 2:
                    if row in judgecomps[str(judgegroup[2])]:  
                        rowtally += 1   # if there is a third judge, add one agreement for the third
                    elif row_opp not in judgecomps[str(judgegroup[2])]:
                        flag += 1 #the pair is not in the third judge's list at all and increase signal not to add this row to the column
                if flag == 0:
                    column.append(int(rowtally/combo_n)) #added Int() so it only counts 1 if all three agree, and only 0 if all three share that pair 
        judgegroupagreement.update({str(judgegroup): column})

        # calculating stats for each row and appending to list for later dictionary & dataframe 
        rowx=sum(judgegroupagreement[str(judgegroup)])
        rown=len(judgegroupagreement[str(judgegroup)])
        maxcomps = (len(scriptlist)*(len(scriptlist)-1))/2
        if rown * 20 > maxcomps: # only if n of shared comparisons > 1/20 possible comparisons
            judges.append(judgegroup) # judges is a key of the dictionary, adding to its values list
            x.append(rowx) # x will be a key, adding to values list
            n.append(rown) # n will be a key, adding to values list
            p.append(rowx/rown) # p will be a key, adding to values list
            std=np.std(judgegroupagreement[str(judgegroup)])
            se.append(std/sqrt(rown)) # se will be a key, adding to values list    
    judgegroupstats.update({'judges': judges, "p": p,"se": se, "x": x, "n": n}) # finally, the dict. to build with keys and value lists
    df = pandas.DataFrame(judgegroupstats) # make a dataframe to pass to the template
    stats_df_indexkey=df.sort_values(by='p', ascending = False) # sort by p highest to lowest
    stats_df=stats_df_indexkey.set_index('judges')
    bestgroupstring = str(stats_df.index[0]) # choose first judgegroup string
    bestgroupids = re.findall('[0-9]+', bestgroupstring) # extract the numeric ids from string
    b = stats_df.iat[0, 0]
    bestagreement = round(b *100, 1)
    bestgroup = []
    for id in bestgroupids:
        bestgroup.append(int(id)) # turn the id strings into integers
    return bestgroup, bestagreement, stats_df                              

def bulkcreatescripts(filepath, user_id, set_id):
    #in python shell define the variable as below
    #filepath="data/set4.csv" 
    #user_id=24 
    #set_id=4
    file = open(filepath, "r", encoding='utf-8-sig')
    csv_reader = csv.reader(file)
    for row in csv_reader:
        id=int(row[0])
        script = Script(set_id=set_id, idcode=id, user_id=user_id)
        script.save()
        print("Created script instance for for idcode ", id, "in set ", set_id, " for user ", user_id)
    return
                
def judgereport(judgeid):
    sets = get_allowed_sets(judgeid)
    report = []
    for set in sets:
        n = Comparison.objects.filter(judge__pk = judgeid, set = set).count()
        scriptcount = Script.objects.filter(set=set).count()
        estcomps = int(scriptcount * (scriptcount-1) * .333)
        report.append([set, n, estcomps])
    df = pandas.DataFrame(report, columns = ["Set","Done So Far","Estimated End"])
    htmltable = df.to_html(index=False)
    return df, htmltable

                     
            

# everything below this line is broken until new chart generator can be found or query can be generated possibly create a model just for each chart?
def get_resultschart(computed_scripts):
    resultsdata = DataPool(
        series=[{
            'options': {
                'source': Script.objects.all() #Script.objects.filter(se__lt=7).order_by('estimated_parameter_in_set')#can't get order by to affect chart x axis yet             
            },
            'terms': [
                'id',
                'estimated_parameter_in_set',
                #'lo95ci',
                #'hi95ci',
            ]
        }]
    )
    cht2= Chart(
        datasource=resultsdata,
        series_options=[{
            'options': {
                'type': 'scatter',
                'linewidth': '1',
            },
            'terms': {
                'id': [ 
                    'estimated_parameter_in_set',
                    #'lo95ci',
                    #'hi95ci',
                ],
            }
        }],
        chart_options={
            'title': {'text': 'Results'},
            'xAxis': {'title':{'text': 'Item Number'}},
            'yAxis': {'title': {'text': 'Estimated & Actual Parameter Value'}},
            'legend': {'enabled': True},
            'credits': {'enabled': True}
            }
    )
    return cht2

def get_scriptchart(computed_scripts):
    scriptdata = DataPool(
        series=[{
            'options': {
                'source':Script.objects.all() #Script.objects.filter(se__lt=7).order_by('estimated_parameter_in_set')#can't get order by to affect chart x axis yet
            },
            'terms': [
                'id',
                'se',
                'stdev',
                'count_same_p',
                'fisher_info',
                'comps_display',
            ]
        }]
    )
    cht = Chart(
        datasource=scriptdata,
        series_options=[{
            'options': {
                'type': 'scatter', 
                'lineWidth': '1',
            },
            'terms': {
                'id': [ 
                    'se', 
                    'stdev', 
                    'count_same_p',
                    'fisher_info',
                    'comps_display',
                ]
            }}
            ],
        chart_options={
            'title': {'text': 'Script Data'}, 
            'xAxis': {'title': {'text': 'Item Number'}}, 
            'yAxis': {'title': {'text': 'Computed SE, Fisher Info, & SD for Development'}}, 
            'legend': {'enabled': True}, 
            'credits': {'enabled': True}
        }
    )
    return cht


# this make_groups() was designed using correlation matrices
""" def make_groups(df):
    similar_groups = []
    ignore = []
    #note: current issue -- makes a group of 1,2,8 where 1 to 2 is .95 and 1 to 8 is .71 but 2 to 8 is .57 
    for col in df.columns:
        for row in df.loc[[col]]: # makes a list of data in each column
            if 0.7 <= df[col][row] < 1.0: # temp values to artificually create a group of 3
                if not col in ignore: # if we already have group [1, 2], we don't want [2, 1]
                    ignore.append(row) 
                    if len(similar_groups) > 0:
                        for group in similar_groups:
                            if group[0] == col:
                                if not row in group:
                                    group.append(row) # add to an existing group 
                                    #print(f"adding {row} to group {group}")                               
                            else: 
                                similar_groups.append([col, row]) # create a new group
                                #print(f"creating group [{col}, {row}] -- not first time")                            
                    else:
                        similar_groups.append([col, row])
                        #print(f"creating group [{col}, {row}] -- first time")  
    #print(df)
    return similar_groups """

""" def interraterb(setobject):
    compdata = []
    comps = Comparison.objects.filter(set=setobject)
    for comp in comps:
        compdata.append([comp.judge.id, comp.scripti.id, comp.scriptj.id, comp.wini])
    compsarray = np.array(compdata)
    judges = list(set(compsarray[:,0])) # set() returns only unique rows in the list which is the first column of the array
    pairs = list(itertools.combinations(judges, 2)) # all possible combinations of judges into pairs
    scriptlist = []
    scripts = Script.objects.filter(set = setobject)
    combosarray =[]
    for script in scripts:
        scriptlist.append(script.id)
    scriptcombos = itertools.combinations(scriptlist, 2) #all possible combinations of script.id into pairs
    agreematrix = pandas.DataFrame(columns=pairs)
    for combo in scriptcombos:
        for pair in pairs: 
            judge1 = [pair[0], combo[0], combo[1], 1] 
            judge2 = [pair[1], combo[0], combo[1], 1]
            if judge1 and judge2 in compdata: #both judges say this pair in this order wins
                print(judge1, "and", judge2, "in compdata")
                agreematrix.append(str(pair): 1, ignore_index=True)
            judge1 = [pair[0], combo[0], combo[1], 0]
            judge2 = [pair[1], combo[0], combo[1], 0]
            if judge1 and judge2 in compdata: #both judges say this pair in this order loses
                print(judge1, "and", judge2, "in compdata")
                agreematrix.append(str(pair): 1, ignore_index=True)
            #still need to check for reverse order
    #once agreematrix is built with column for each pair and values that show agreement for that combo and that pair
    #then add up each column and select the judges with the greatest sum of agreement among eachother
    return pairs, compdata, compsarray, scriptcombos, combosarray """
    