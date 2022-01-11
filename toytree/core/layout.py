#!/usr/bin/env python

"""Get node coordinate layouts from a tree and style arguments.

This class is primarily intended for internal use.

The Layout class will parse the style args to project Nodes into 
their proper coordinates for plotting. This is done very quickly
using cached heights, but if fixed-order or fixed-position args are
used then it requires a tree traversal and to make a copy of the 
style dict.

TODO: move tip angle estimation code to this module, since it will 
be relevant for unrooted tree layouts.
"""

from typing import List, TypeVar
from copy import deepcopy
import numpy as np
from loguru import logger
from toytree.core.style.tree_style import get_tree_style, TreeStyle, SubStyle
from toytree.utils import ToytreeError

ToyTree = TypeVar("ToyTree")
ogger = logger.bind(name="toytree")


class Layout:
    """Layout class to get Node drawing coordinates given style args.

    Style args affecting the node layout projection include:
        'layout': 'r', 'l', 'u', 'd', 'c', 'cx-y', '*'
        ...

    """
    def __init__(self, tree, **kwargs):
        self.tree = tree
        self.style: TreeStyle = None
        self.coords: np.ndarray = None
        self.fixed_order: List[str] = kwargs.pop('fixed_order', None)
        self.fixed_position: List[float] = kwargs.pop('fixed_position', None)

        # set base_style and style
        self.get_style(kwargs)
        self.run()

    def get_style(self, kwargs):
        """Return a style class object updated by user-args.

        If not tree_style arg was entered this creates a copy of the 
        current tree's .style object to apply user-args onto.
        """
        # extract layout, use_edge_lengths and tip_labels_align from ts
        if kwargs.get("ts"):
            kwargs["tree_style"] = kwargs.pop("ts")

        # get tree_style object (entered, from tree, or new) 
        if kwargs.get('tree_style'):
            self.style = get_tree_style(kwargs['tree_style'][0])
        elif self.tree.style.tree_style is not None:
            self.style = get_tree_style(self.tree.style.tree_style)
        else:
            self.style = deepcopy(self.tree.style)

        # update base style with user entered style kwargs
        for key, value in kwargs.items():

            # skip key if left at default value (None)
            if value is None:
                continue

            # check if it is a substyledict
            substyle = getattr(self.style, key)

            # update value of a standard style argument
            if not isinstance(substyle, SubStyle):
                setattr(self.style, key, value)

            # update a substyle dict
            else:
                for sub_key in value:
                    sub_value = value[sub_key]
                    sub_key = sub_key.replace("-", "_")  # for -toyplot-anchor-shift, etc.
                    if hasattr(substyle, sub_key):
                        setattr(substyle, sub_key, sub_value)
                    else:
                        logger.warning(
                            f"Unrecognized substyle drawing arg skipped: {sub_key}")

    def run(self):
        """Sets the .coords array with x, y coordinates."""

        # get coordinates from current x,y attributes unless fixed args
        if (self.fixed_order is None) and (self.fixed_position is None):
            self.coords = self.tree._get_node_coordinates()
        else:
            self.coords = self._get_fixed_order_and_position_coords()

        # update coordinates given style args.
        self._update_coordinates()

    def _update_coordinates(self):
        """Set starting values that will be updated by style args.
        
        For a linear layout this represents the the xbaseline coords
        of the tips if they were aligned, and similarly for a circular
        layout it is the aligned tip radial positions, with the radial
        start and end points default to 0-360, or less if specified.
        TODO: For unrooted layout this is ...
        """
        # override all coordinates. Sets all edge lengths to 1.
        if not self.style.use_edge_lengths:
            self._assign_unit_length_edges()

        # modify coordinates from starting 'down-facing' layout
        if self.style.layout in 'rlud':

            # align tips at 0 is done later, since they are diff edges.
            # if self.style['tip_labels_align']:
                # self.coords[:self.tree.ntips, 1] = 0

            # change baseline
            self.coords[:, 0] += self.style.xbaseline
            self.coords[:, 1] += self.style.ybaseline

            # re-orient to right, left or down.
            if self.style.layout == "u":
                self.coords[:, 1] *= -1
            if self.style.layout == "l":
                self.coords = self.coords[:, [1, 0]]
            if self.style.layout == "r":
                self.coords = self.coords[:, [1, 0]]
                self.coords[:, 0] *= -1

        # get radial coordinates of tips from r0 - rN. Here the root
        # is at position (0, 0) and the tips are radially surrounding.
        else:
            raise NotImplementedError("radial todo")

    def _assign_unit_length_edges(self):
        """When use_edge_length=False this sets all dists to unit 1"""
        for node in self.tree.traverse("postorder"):
            if node.is_leaf():
                self.coords[node.idx, 1] = 0
            else:
                cys = [self.coords[child.idx, 1] for child in node.children]
                self.coords[node.idx, 1] = max(cys) + 1

    def _get_fixed_order_and_position_coords(self):
        """Return coords using fixed args. Requires a tree traversal.

        The idx order of the tips is overriden to re-order them
        according an ordered list of names. This is often used to
        visualize discordance among different trees.
        """
        # get user fixed-positions or use the default range of 0-Ntips
        if self.fixed_position is None:
            positions = np.arange(self.tree.ntips)
        else:
            positions = np.array(self.fixed_position)
            assert positions.size == self.tree.ntips, (
                "fixed_position arg must be same len as ntips.")

        # get user fixed-order as the index of tip name strings
        if self.fixed_order is None:
            idxorder = np.arange(self.tree.ntips)
        else:
            idxorder = np.zeros(self.tree.ntips, dtype=int)
            assert len(self.fixed_order) == self.tree.ntips, (
                "fixed order arg must be same len as ntips.")

            # get indices at which user wants Nodes to be displayed
            tipnames = self.tree.get_tip_labels()
            for idx, name in enumerate(self.fixed_order):
                if name not in tipnames:
                    raise ToytreeError(f"name {name} not in tree.")
                idxorder[tipnames.index(name)] = idx

        # return coordinates using the new fixed_order
        coords = []
        for node in self.tree.traverse("idxorder"):
            if node.is_leaf():
                newx = positions[idxorder[node.idx]]
                coords.append((newx, node._height))
            else:
                newx = np.mean([coords[i.idx][0] for i in node.children])
                coords.append((newx, node._height))
        return np.array(coords)


def equal_daylight_algorithm(tree: ToyTree, max_iter: int=1) -> float:
    """Return coordinates for unrooted layout under the eda algorithm.
    
    This algorithm equalizes the sizes of angular gaps between 
    subtrees. As Felsenstein said, the result is "outstanding".

    References
    ----------
    - Felsenstein 2004, page 582 (and see Figure 34.6).
    """
    # get the equal angle algorithm tree as a starting tree.
    coords = equal_angle_algorithm(tree)

    # get all leaves as a set
    leaves = {tree[i] for i in range(tree.ntips)}

    # visit each internal node.
    for nidx in range(tree.ntips, tree.nnodes)[::-1]:

        # select this internal node and its current coordinates
        node = tree[nidx]
        pos = coords[nidx]

        # get the 3 or more subtrees from this vertex
        subsets = [set(i.get_leaves()) for i in node.children]
        subsets.append(leaves - set.union(*subsets))

        # record where the light and shade is...
        light = []
        shade = []

        # get daylight between subtrees as lines from this node to 
        # their tips, finding largest windows.
        for subset in subsets:
            for node in subset:
                npos = coords[node.idx]

                # line is
                delta_x = pos[0] - npos[0]
                delta_y = pos[1] - npos[1]
                print(f"{nidx},{node.name}, {np.rad2deg(np.arctan(delta_y / delta_x)):.3f}")



def equal_angle_algorithm(tree: ToyTree) -> float:
    """Return coordinates for unrooted layout under the 'eaa' algorithm.

    Assign the root node a sector from 0-360 degrees, and divide each
    descendent node into subsectors with size weighted by their n
    descendants.

    References
    ----------
    - Felsenstein (2004), page 578.
    """
    coords = np.zeros(shape=(tree.nnodes, 2))

    # if tree is rooted then use root Node as the central vertex.
    ntips = tree.ntips
    radians_per_tip = 2 * np.pi / ntips

    # record the sum of sector area for each Node as its N 
    # descendants * the radians per tip.
    for node in tree.traverse("postorder"):
        if node.is_leaf():
            node.radian_sum = radians_per_tip
        else:
            node.radian_sum = sum(i.radian_sum for i in node.children)

    # assign radian sectors in levelorder.
    for node in tree.traverse("levelorder"):
        if node.is_root():
            coords[node.idx] = (0, 0)
            node.sector = [0, 2 * np.pi]
        else:
            cohort = node.up.children
            idx = cohort.index(node)
            if not idx:
                start = node.up.sector[0]
            else:
                start = cohort[idx - 1].sector[1]
            node.sector = [start, start + node.radian_sum]
            mid = sum(node.sector) / 2.

            # geometry relative to parent position and angle
            parent_pos = coords[node.up.idx]
            hypo = node.dist
            newx = parent_pos[0] + (hypo * np.sin(mid))
            newy = parent_pos[1] - (hypo * np.cos(mid))            
            coords[node.idx] = (newx, newy)
    return coords


if __name__ == "__main__":

    import toytree
    tre = toytree.rtree.unittree(6)
    lay = Layout(
        tre, 
        layout='d', 
        fixed_order=tre.get_tip_labels()[::-1],
        fixed_position=None,
        xbaseline=10,
    )
    # print(lay.coords)

    # NWK = "(((((((A:4,B:4):6,C:5):8,D:6):3,E:21):10,((F:4,G:12):14,H:8):13):13,((I:5,J:2):30,(K:11,L:11):2):17):4,M:56);"
    NWK = "(((E,F),(G, H)),((C,D),(B,(I,J)),A));"
    TRE = toytree.tree(NWK)
    #TRE._draw_browser(ts='s', use_edge_lengths=True)
    # print(equal_angle_algorithm(TRE))
    print(equal_daylight_algorithm(TRE))
    # print(equal_daylight_algorithm(tre))

    # lay = Layout(
    #     tre, 
    #     layout='c', 
    #     fixed_order=tre.get_tip_labels()[::-1],
    #     fixed_position=None,
    #     xbaseline=10,
    # )
    # print(lay.coords)

    # lay = Layout(
    #     tre, 
    #     layout='c0-180', 
    #     fixed_order=tre.get_tip_labels()[::-1],
    #     fixed_position=None,
    #     xbaseline=10,
    # )
    # print(lay.coords)

    # # unrooted layout 
    # lay = Layout(
    #     tre, 
    #     layout="*",
    #     fixed_order=tre.get_tip_labels()[::-1],
    #     fixed_position=None,
    #     xbaseline=10,
    # )
    # print(lay.coords)
