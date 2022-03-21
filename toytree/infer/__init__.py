#!/usr/bin/env python

"""toytree inference subpackage.


"""

from toytree.infer.src.upgma import infer_upgma_tree
from toytree.infer.src.neighbor_joining import infer_neighbor_joining_tree
from toytree.infer.src.maximum_likelihood import JC69, K80, TN93
