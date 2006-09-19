
import condorMonitor

#
# condor_q dict = {schedd_name:condorq}
#
def findNeed(condorq_dict,attr_list):
    qcount = condorMonitor.SummarizeMulti(condor_q_dict.values(),lambdahash_func)


############################################################
#
# I N T E R N A L - Do not use
#
############################################################

def hash_attr(attr_list,el):
    out=[]
    for attr in attr_list:
        out.append(el[attr])
    return out

