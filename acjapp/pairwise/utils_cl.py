
from .models import Item, Comparison, Group
import pandas
import csv


# used from the django manage.py python shell
def bulkcreateitems(filepath, user_id, group_id):
    # in python shell define the variable as this example
    # bulkcreateitems("data/set4.csv",24,4)
    file = open(filepath, "r", encoding='utf-8-sig')
    csv_reader = csv.reader(file)
    for row in csv_reader:
        id=int(row[0])
        item = Item(group_id=group_id, idcode=id, user_id=user_id)
        item.save()
        print("Created item instance for idcode ", id, "in group ", group_id, " for user ", user_id)
    return

# used from the django manage.py python shell
# usage example: a, b = judgereport(30)
def judgereport(judgeid):
    groups = get_allowed_groups(judgeid)
    report = []
    for group in groups:
        n = Comparison.objects.filter(judge__pk = judgeid, group = group).count()
        itemcount = Item.objects.filter(group=group).count()
        groupobject = Group.objects.get(pk=group)
        if groupobject.override_end == None:
            maxcomps = int(itemcount * (itemcount-1) * .333)
        else:
            maxcomps = groupobject.override_end
        report.append([group, n, maxcomps])
    df = pandas.DataFrame(report, columns = ["Group","Done So Far","End"])
    htmltable = df.to_html(index=False)
    return df, htmltable

# used from the django manage.py python shell
# usage example: a,b,c,d,e = groupstats(4, [1,27,26],[36,35,38])
def groupstats(group, judgelist1, judgelist2):
    computed_items = get_computed_items(group, judgelist1)
    rankorder1_df = pandas.DataFrame([item.__dict__ for item in computed_items ]) # convert list of objects into a dataframe
    rankorder1_df.drop(['idcode_f', 'fisher_info', 'samep', 'randomsorter', 'percentile','comps','wins','stdev','probability','se','ep','lo95ci','hi95ci'], axis = 1, inplace=True) # drop unneeded columns
    idorder1_df = rankorder1_df.sort_values("id")
    if judgelist2 == []:
        rankorder2_df = "None"
        idorder2_df = "None"
        rankcorr_df = "None"
    else:
        computed_items = get_computed_items(group, judgelist2)
        rankorder2_df = pandas.DataFrame([item.__dict__ for item in computed_items ])
        rankorder2_df.drop(['idcode_f', 'fisher_info', 'samep', 'randomsorter', 'percentile','comps','wins','stdev','probability','se','ep','lo95ci','hi95ci'], axis = 1, inplace=True) # drop unneeded columns
        idorder2_df = rankorder2_df.sort_values("id")
        rankcorr_df = idorder1_df.corrwith(idorder2_df, axis = 0, method = "spearman")
    return rankorder1_df, idorder1_df, rankorder2_df, idorder2_df, rankcorr_df