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

# stats methods reference: http://personal.psu.edu/abs12/
# Aleksandra B. Slavković | Professor of Statistics
# Department of Statistics, Penn State University, University Park, PA 16802

from .models import Item, Comparison, Group
import numpy as np
from numpy import log, sqrt
import random
import itertools
from operator import itemgetter
import pandas
from scipy.stats import spearmanr, percentileofscore

class ComputedItem:
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

def get_allowed_groups(userid):
    groups = Group.objects.filter(judges__id__exact=userid).order_by('pk')
    allowed_groups_ids = []
    for group in groups:
        allowed_groups_ids.append(group.id)
    return allowed_groups_ids

def item_selection(group, userid):
    itemcount = Item.objects.filter(group=group).count()
    group_object = Group.objects.get(pk=group) # sometimes we need to use object not just the string of the group ID number
    compslist = build_compslist(group, userid)
    judges = [userid] #judges must be a list, even if it only has one judge in it
    computed_items_for_user_in_group = get_computed_items(group, judges)
    maxcomps=(itemcount * (itemcount-1)/2)
    switch=min(itemcount + (itemcount * (itemcount-1)/6), maxcomps)
    if len(compslist) < switch: #prioritize minimum comps until comps = min of n+max/3 or max, then . . .
        computed_items_for_user_in_group.sort(key = lambda x: (x.comps, x.samep, x.fisher_info, x.randomsorter))
    else: #prioritize lowest same probability (less distinct estimate < -1, samep = -1 indicates unique estimate)
        computed_items_for_user_in_group.sort(key = lambda x: (x.samep, x.comps, x.fisher_info, x.randomsorter))
        if computed_items_for_user_in_group[0].samep == -1 and group_object.override_end == None:
            return compslist, None, None, [] # everything is empty

    # Go through all comparable items, and choose the first as itemi.
    # Then calculate the difference in probability 'p_diff' between itemi and every other item
    j_list = []
    for i, item in enumerate(computed_items_for_user_in_group):
        if i == 0:
            if item.comps == itemcount-1:
                return compslist, None, None, [] # everything is empty
            itemi = Item.objects.get(pk = item.id)
            p_i = float(item.probability)
        elif [itemi.id, item.id] not in compslist and [item.id, itemi.id] not in compslist: # don't consider this for itemj if it's already been compared
            p_j = float(item.probability)
            p_diff = round(abs(p_i - p_j),3)
            j_list.append([item.id, p_diff, item.comps, item.samep, item.fisher_info, item.randomsorter])

    # Based on lowest probability difference, then random index, choose the most similar item to display as itemj
    if j_list:
        j_list.sort(key=itemgetter(1,5)) # 1 is p_diff, 5 is randomsorter
        itemj = Item.objects.get(pk = j_list[0][0]) # the item that has the smallest log odds difference (lodiff)
    else: # if there are no possibilities, we can't choose a itemj at all. whatever recieves the request will have to deal with a NoneType
        j_list = []
        itemj = None
    return compslist, itemi, itemj, j_list

def get_computed_items(group, judges):
    eps_of_group = []
    computed_items_for_user_in_group =[]
    items = Item.objects.filter(group=group)
    for item in items:
        comps, wins = compute_comps_wins(item, judges)
        logit, probability, stdev, fisher_info, se, ep, hi95ci, lo95ci, randomsorter = compute_more(comps, wins)
        computed_items_for_user_in_group.append(
            ComputedItem(
                item.id,
                item.idcode,
                item.idcode_f,
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
                0, # samep is set separately
                0, # rank is set separately
                randomsorter,
                0, # percentile is set separately
                )
        )
    computed_items_for_user_in_group = set_ranks(computed_items_for_user_in_group)
    return computed_items_for_user_in_group

def build_compslist(group, userid):
    comps = Comparison.objects.filter(group=group).filter(judge=userid)
    compslist = []
    for comp in comps:
        i = comp.itemi.id
        j = comp.itemj.id
        compslist.append([i, j])
    return compslist

def compute_comps_wins(item, judges):
    comps = .001 # prevents divide-by-zero error in calculating probability
    wins = 0
    for judge in judges:
        #count all the comparisons each item has been involved in for user
        comparisons_as_i_for_judge_count = Comparison.objects.filter(itemi=item, judge__pk=judge).count()
        comparisons_as_j_for_judge_count = Comparison.objects.filter(itemj=item, judge__pk=judge).count()
        thisjudgecomps = comparisons_as_i_for_judge_count + comparisons_as_j_for_judge_count

        #count all the comparisons this item has won
        wins_as_i_for_judge_count = Comparison.objects.filter(wini=1, itemi=item, judge__pk=judge).count()
        wins_as_j_for_judge_count = Comparison.objects.filter(wini=0, itemj=item, judge__pk=judge).count()
        thisjudgewins = wins_as_i_for_judge_count + wins_as_j_for_judge_count

        comps += thisjudgecomps
        wins += thisjudgewins
    return comps, wins

def compute_more(comps, wins):
    #compute probability of winning for each item based on comparisons so far
    probability = wins/(comps) # comps comes in with a .001 so no error dividing by 0
    # probability = (wins + .5)/(comps + 1) # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 23
    # compute the standard deviation of sample of comparisons for this item
    stdev = sqrt(((((1 - probability) ** 2) * wins) + (((0 - probability) ** 2) * (int(comps) - wins))) / (comps + .001))
    #compute other attributes only if not all wins or all losses so far
    if (round(probability, 3) == 1) or (probability <= 0):
        logit = None
        fisher_info = 0
        se = None
        ep = None
        hi95ci = None
        lo95ci = None
    else:
        se = round(stdev / sqrt(comps),3)
        # standard error of p scale measures variability of the sample mean about the true mean
        # see https://personal.psu.edu/abs12/stat504/Lecture/lec3_4up.pdf slide 13
        logit = round(log(probability/(1 - probability)), 3) # also called the MLE of phi φ
        fisher_info = comps * probability * ( 1 - probability) # slide 33 the fisher information for phi
        # see http://personal.psu.edu/abs12//stat504/online/01b_loglike/10_loglike_alternat.htm
        # "an asymptotic confidence interval constructed on the φ scale will be more accurate in coverage than an interval constructed on the p scale"
        # note: the CI for logit is fine for this, we don't need to transform it back to p as in this article
        ci = 1.96 * sqrt(1/fisher_info) # 95% CI of at the MLE of phi--see slide 30
        logithi95 = logit + ci
        logitlo95 = logit - ci
        b = 10 # determine the spread of parameter values
        a = int(100 - (3.18 * b )) # aim for max parameter of 100 for logit=3.18 / p = .96)
        ep = round((logit * b), 1) + a
        hi95ci = round((((logithi95) * b) + a), 1)
        lo95ci = round((((logitlo95) * b) + a), 1)

    randomsorter = random.randint(0,1000)
    return logit, probability, stdev, fisher_info, se, ep, hi95ci, lo95ci, randomsorter
    # more here: http://personal.psu.edu/abs12//stat504/online/01b_loglike/01b_loglike_print.htm

def set_ranks(computed_items_for_user_in_group):
    #now decrease (for sorting later) samep by one for every item including self with matching probability and set a rank value fo each
    item_ranks = []
    computed_items_for_user_in_group.sort(key = lambda x: x.probability, reverse=True)
    rank = 0
    for item in computed_items_for_user_in_group:
        for match in computed_items_for_user_in_group:
            if match.probability == item.probability:
                match.samep -= 1
        if item.samep == -1: #if there's only one at that value, then increase rank increment 1 for next
            rank += 1
        item.rank = rank
        item_ranks.append(len(computed_items_for_user_in_group)-rank)
    # calculate percentile in this group using the list of ranks in group
    for item in computed_items_for_user_in_group:
        r = len(item_ranks)-item.rank
        perc = percentileofscore(item_ranks, float(r), kind='strict')
        item.percentile = '{:.2f}'.format(perc)
    return computed_items_for_user_in_group

def make_groups(groupid, judgelist):
    groupobject = Group.objects.get(pk=groupid)
    if judgelist == []: #judgelist is only used from command line to get combined stats for a group of preselected judges
        try: # if comps exist for this group, query a list of unique judge ids who have made comparisons on this group
            judgelist = Comparison.objects.filter(group=groupobject).values_list('judge_id', flat=True).distinct()
        except:
            judgelist = None
    if len(judgelist) == 1:
        bestgroup = []
        bestagreement = 0
        corrstats_df = None
        return bestgroup, bestagreement, corrstats_df, None
    set_judge_item_rank = {}
    for judge in judgelist:
        computed_items = get_computed_items(groupobject, [judge])
        computed_items.sort(key = lambda x: x.id)
        set_judge_item_rank[judge]=[]
        for item in computed_items:
            set_judge_item_rank[judge].append(item.rank)
    if len(judgelist) == 2:
        coef, p = spearmanr(set_judge_item_rank[0],set_judge_item_rank[1])
        bestgroup = judgelist
        bestagreement = coef
        corrstats_df = pandas.DataFrame(set_judge_item_rank)
        return bestgroup, bestagreement, corrstats_df, None
    else:
        judgepairs = itertools.combinations(judgelist, 2)
        judgepaircorr = {}
        corr_chart_data=[]
        for judgepair in judgepairs:
            judge1 = judgepair[0]
            judge2 = judgepair[1]
            coef, p = spearmanr(set_judge_item_rank[judge1], set_judge_item_rank[judge2])
            judgepaircorr[judgepair]=[coef, p]
            if coef >= .6:
                corr_chart_data.append([str(judge1), str(judge2), round(coef,3)])
        

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
    corrstats_df = df_sorted.set_index('Judge Group')
    b = corrstats_df.iat[0, 0]
    bestagreement = round(b,3)
    bestgroup = pandas.DataFrame.first_valid_index(corrstats_df)
    return bestgroup, bestagreement, corrstats_df, corr_chart_data
