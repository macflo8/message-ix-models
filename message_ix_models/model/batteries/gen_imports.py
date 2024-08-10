from unittest import result
import pandas as pd
import numpy as np
from collections import defaultdict
from message_ix_models.util import broadcast, same_node
import message_ix

from message_ix.utils import make_df
import ixmp
import message_data
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


def gen_imports (results, scenario):



    #Removed the following two lines because now this file is used by global model.
    #More regions to work with

    exports_df = results['output'] 

    imports = exports_df[exports_df['technology'].str.contains('export')].copy()

    imports['technology'] = imports['technology'].replace('export','import', regex = True)
    imports['level'] = imports['level'].replace('export','final', regex = True)
    imports.rename(columns = {'node_loc' :'node_dest', 'node_dest' : 'node_loc'})


    scenario.check_out()
    for k, v in imports.items():
        scenario.add_par(k,v)


    return scenario

