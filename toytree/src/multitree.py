#!/usr/bin/env python

"""
MultiTree objects

TODO: 
    - re-do support for BPP weird format trees.
    - set-like function that drops tips from each tree not shared by all trees.
    - root function that drops tree that cannot be rooted or not set-like
    - consensus function drop tips that are not in set.
    - treegrid simplify args (3, 3) e.g., will make a 600x600 canvas...
    - Annotate class for surrounding markers...
    - A distinct multitree mark for combining styles on topologies 
    - New mark: leave proper space for tips to mtree fits same as tree.
"""

from typing import Union, Iterable, Optional
from copy import deepcopy
from pathlib import Path
import numpy as np

from toytree.src.tree import ToyTree
from toytree.src.consensus import ConsensusTree
from toytree.src.io.TreeParser import TreeParser
from toytree.src.drawing.tree_style import TreeStyle
from toytree.src.drawing.style_checker import StyleChecker
from toytree.src.drawing.canvas_setup import GridSetup, CanvasSetup
from toytree.src.drawing.render import ToytreeMark
from toytree.utils.exceptions import ToytreeError


def mtree(
    data:Union[str, Path, Iterable[ToyTree]],
    tree_format:int=0,
    ):
    """
    General class constructor to parse and return a MultiTree class 
    object from input arguments as a multi-newick string, filepath,
    Url, or Iterable of Toytree objects.
    
    data (Union[str, Path, Iterable[ToyTree]]):
        string, filepath, or URL for a newick or nexus formatted list 
        of trees, or an iterable of ToyTree objects.

    Examples:
    ----------
    mtre = toytree.mtree("many_trees.nwk")
    mtre = toytree.mtree("((a,b),c);\n((c,a),b);")
    mtre = toytree.mtree([toytree.rtree.rtree(10) for i in range(5)])
    """
    # parse the newick object into a list of Toytrees
    treelist = []
    if isinstance(data, Path):
        data = str(Path)
    if isinstance(data, str):
        tns = TreeParser(data, tree_format, multitree=True).treenodes
        treelist = [ToyTree(i) for i in tns]
    elif isinstance(data[0], ToyTree):
        treelist = data
    else:
        raise ToytreeError("mtree input format unrecognized.")
    return MultiTree(treelist)
        # set tip plot order for treelist to the first tree order
        # order trees in treelist to plot in shared order...
        # self._fixed_order = fixed_order   # (<list>, True, False, or None)
        # self._user_order = None
        # self._cons_order = None
        # self._set_tip_order()
        # self._parse_treelist()



class BaseMultiTree:
    def __init__(self):
        self.style = TreeStyle('m')
        self._i = 0
        self.treelist = []


# class MultiTree2(BaseMultiTree):
#     pass


# class MixedTree(BaseMultiTree):
#     pass


class MultiTree:
    """
    Toytree MultiTree object for plotting or extracting stats from
    a set of trees sharing the same tips. 

    Parameters:
    -----------
    data: List[ToyTrees]
        
    tree_format: (int)
        ete format for newick tree structure. Default is 0. 
    fixed_order: (bool, list, None)    
        ...

    Attributes:
    -----------
    treelist: list
        A list of toytree objects from the parsed newick file. 

    Functions():
    ------------
    get_consensus_tree: 
        Returns a ToyTree object with support values on nodes.
    draw_cloud_tree:
        Draws a plot with overlapping fixed_order trees.
    draw
        Draws a plot with n x m trees in a grid.
    """
    def __init__(self, treelist):

        # setting attributes
        self._i = 0
        self.style = TreeStyle('m')
        self.treelist = treelist

    def __len__(self):  
        return len(self.treelist)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            result = self.treelist[self._i]
        except IndexError as err:
            self._i = 0
            raise StopIteration from err
        self._i += 1
        return result

    @property
    def ntips(self):
        "returns the number of tips in each tree."
        return self.treelist[0].ntips

    @property
    def ntrees(self):
        "returns the number of trees in the MultiTree treelist."
        return len(self.treelist)

    @property
    def all_tips_shared(self):
        """
        Check if names are the same in all the trees in .treelist.
        """
        alltips_shared = all([
            set(self.treelist[0].get_tip_labels()) == set(i.get_tip_labels()) 
            for i in self.treelist
        ])
        if alltips_shared:
            return True
        return False

    # TODO: this could be sped up by using toytree copy command.
    def copy(self):
        return deepcopy(self)

    def write(
        self, 
        path: Optional[Path], 
        tree_format:int=0,
        features: Optional[Iterable[str]]=None,
        dist_formatter:str="%0.6g",
        ) -> Optional[str]:
        """
        Writes a multi-line string of newick trees to stdout or filepath
        """
        treestr = "\n".join([
            i.write(
                path=None, 
                tree_format=tree_format, 
                features=features,
                dist_formatter=dist_formatter,
            )
            for i in self.treelist]
        )
        if not path:
            return treestr
        with open(path, 'w') as outtre:
            outtre.write(treestr)
        return None


    def reset_tree_styles(self):
        """
        Sets the .style toytree drawing styles to default for all ToyTrees
        in a MultiTree .treelist. 
        """
        for tre in self.treelist:
            tre.style = TreeStyle('n')


    # -------------------------------------------------------------------
    # Tree List Statistics or Calculations
    # -------------------------------------------------------------------
    # def get_tip_labels(self):
    #     """
    #     Returns the tip names in tree plot order for the *list of tree*, 
    #     starting from the zero axis. If all trees in the treelist do not 
    #     share the same set of tips then this will return an error message. 

    #     If fixed_order is a user entered list then names are returned in that
    #     order. If fixed_order was True then the consensus tree order is 
    #     returned. If fixed_order was None or False then the order of the first
    #     ToyTree in .treelist is returned. 
    #     """
    #     if not self.all_tips_shared:
    #         raise Exception(
    #             "All trees in treelist do not share the same set of tips")
    #     return self.treelist[0].get_tip_labels()


    def get_consensus_tree(self, cutoff=0.0, best_tree=None):
        """
        Returns an extended majority rule consensus tree as a Toytree object.
        Node labels include 'support' values showing the occurrence of clades 
        in the consensus tree across trees in the input treelist. 
        Clades with support below 'cutoff' are collapsed into polytomies.
        If you enter an optional 'best_tree' then support values from
        the treelist calculated for clades in this tree, and the best_tree is
        returned with support values added to nodes. 

        Params
        ------
        cutoff (float; default=0.0): 
            Cutoff below which clades are collapsed in the majority rule 
            consensus tree. This is a proportion (e.g., 0.5 means 50%). 
        best_tree (Toytree or newick string; optional):
            A tree that support values should be calculated for and added to. 
            For example, you want to calculate how often clades in your best 
            ML tree are supported in 100 bootstrap trees. 
        """
        if best_tree is not None:
            if not isinstance(best_tree, ToyTree):
                best_tree = ToyTree(best_tree)
        cons = ConsensusTree(self.treelist, best_tree=best_tree, cutoff=cutoff)
        cons.update()
        return cons.ttree




    def draw(
        self, 
        nrows=1, 
        ncols=4, 
        shared_axes=False,
        idxs=None, 
        width=None,
        height=None,
        **kwargs):
        """
        Draw a set of trees on a grid with nice spacing and optionally with
        a shared axes. Different styles can be set on each tree individually
        or set here during drawing to be shared across trees.

        Parameters:
        -----------
        nrows (int):
            Number of grid cells in x dimension (default=1)
        ncols (int):
            Number of grid cells in y dimension (default=4)
        shared_axes (bool):
            If True then the 'height' dimension will be shared among 
            all trees so heights are comparable, otherwise each tree is 
            scaled to fill the space in its grid cell.
        idxs (int):
            The indices of trees in treelist that you want to draw. By 
            default the first ncols*nrows trees are drawn, but you can 
            select the 10-14th tree by entering idxs=[10,11,12,13]
        width (int):
            Width of the canvas
        height (int):
            Height of the canvas
        kwargs (dict):
            Any style arguments supported by .draw() in toytrees.
        """
        # get index of trees that will be drawn
        if idxs is None:
            tidx = range(0, min(nrows * ncols, len(self.treelist)))
        else:
            tidx = idxs

        # get the trees
        treelist = [self.treelist[i] for i in tidx]
        if kwargs.get("fixed_order") is True:
            fixed_order = (
                MultiTree(treelist)
                .get_consensus_tree()
                .get_tip_labels()
            )
            kwargs["fixed_order"] = fixed_order

        # if less than 4 trees reshape ncols,rows,
        if len(treelist) < 4:
            if nrows > ncols:
                nrows = len(treelist)
                ncols = 1
            else:
                nrows = 1
                ncols = len(treelist)

        # get layout first from direct arg then from treestyle
        if "ts" in kwargs:
            layout = TreeStyle(kwargs.get("ts")).layout
        elif "treestyle" in kwargs:
            layout = TreeStyle(kwargs.get("ts")).layout
        elif "layout" in kwargs:
            layout = kwargs.get("layout")
        else:
            layout = "r"

        # get the canvas and axes that can fit the requested trees.
        grid = GridSetup(nrows, ncols, width, height, layout)
        canvas = grid.canvas
        axes = grid.axes

        # max height of trees in treelist for shared axes
        maxh = max([t.treenode.height for t in treelist])

        # default style 
        if "tip_labels_style" in kwargs:
            if "-toyplot-anchor-shift" not in kwargs["tip_labels_style"]:
                kwargs["tip_labels_style"]["-toyplot-anchor-shift"] = "10px"
            if "font-size" not in kwargs["tip_labels_style"]:
                kwargs["font-size"] = "9px"
        else:
            kwargs["tip_labels_style"] = {
                "-toyplot-anchor-shift": "10px",
                "font-size": "9px",
            }           

        # add toytree-Grid mark to the axes
        marks = []
        for idx in range(grid.nrows * grid.ncols):

            # get the axis
            ax = grid.axes[idx]

            # add the mark
            _, _, mark = treelist[idx].draw(axes=ax, padding=10, **kwargs.copy())

            # store the mark
            marks.append(mark)

            # make tip labels align on shared axes if tip labels
            shrink = (kwargs.get("shrink") if kwargs.get("shrink") else 0)

            if shared_axes:
                if not all([i is None for i in mark.tip_labels]):
                    if mark.layout == "r":
                        ax.x.domain.max = maxh * 0.5 + shrink
                    elif mark.layout == "l":
                        ax.x.domain.min = -maxh * 0.5 - shrink
                    elif mark.layout == "d":
                        ax.y.domain.min = -maxh * 0.5 - shrink
                    elif mark.layout == "u":
                        ax.y.domain.max = maxh * 0.5 + shrink

            # set shared axes
            if shared_axes:
                if mark.layout == "r":
                    ax.x.domain.min = -maxh
                elif mark.layout == "l":
                    ax.x.domain.max = maxh
                elif mark.layout == "d":
                    ax.y.domain.max = maxh
                elif mark.layout == "u":
                    ax.y.domain.min = -maxh

            # axes off if not scalebar
            if not kwargs.get("scalebar") is True:
                ax.show = False

        # add mark to axes
        return canvas, axes, marks



    # def draw_tree_grid(
    #     self, 
    #     axes=None,
    #     nrows=None, 
    #     ncols=None, 
    #     start=0, 
    #     fixed_order=False, 
    #     shared_axis=False, 
    #     **kwargs):
    #     """        
    #     Deprecated. Tree grid drawing are now produced with .draw().
    #     """
    #     raise DeprecationWarning(
    #         ".draw_tree_grid() has been replaced by the .draw() function."
    #     )


    def draw_cloud_tree(self, axes=None, fixed_order=None, jitter=0.0, **kwargs):
        """
        Draw a series of trees overlapping each other in coordinate space.
        The order of tip_labels is fixed in cloud trees so that trees with 
        discordant relationships can be seen in conflict. To change the tip
        order enter a list of names to 'fixed_order'.

        Parameters:
        -----------
        axes: (None or toyplot.coordinates.Cartesian)
            If None then a new Canvas and Cartesian axes object is returned,
            otherwise if a Cartesian axes object is provided the cloudtree
            will be drawn on the axes.      

        **kwargs: 
            All drawing style arguments supported in the .draw() function 
            of toytree objects are also supported by .draw_cloudtree().
        """
        # canvas styler
        fstyle = TreeStyle('n')
        fstyle.width = (kwargs.get("width") if kwargs.get("width") else None)
        fstyle.height = (kwargs.get("height") if kwargs.get("height") else None)
        fstyle.tip_labels = self.treelist[0].get_tip_labels()
        fstyle.layout = (kwargs.get("layout") if kwargs.get("layout") else 'r')
        fstyle.padding = (kwargs.get("padding") if kwargs.get("padding") else 20)
        fstyle.scalebar = (kwargs.get("scalebar") if kwargs.get("scalebar") else False)
        fstyle.use_edge_lengths = (kwargs.get("use_edge_lengths") if kwargs.get("use_edge_lengths") else True)
        fstyle.xbaseline = (kwargs.get("xbaseline") if kwargs.get("xbaseline") else 0)
        fstyle.ybaseline = (kwargs.get("ybaseline") if kwargs.get("ybaseline") else 0)

        # get canvas and axes
        cs = CanvasSetup(self, axes, fstyle)
        canvas = cs.canvas
        axes = cs.axes

        # fix order treelist
        if not isinstance(fixed_order, list):
            fixed_order = (
                MultiTree(self.treelist)
                .get_consensus_tree()
                .get_tip_labels()
            )

        # add trees
        for tidx, tree in enumerate(self.treelist):

            # the default MultiTree object style.
            curstyle = self.style.copy()

            # allow THIS tree to override some edge style args
            curstyle.edge_style.update(tree.style.edge_style)
            curstyle.edge_colors = tree.style.edge_colors
            curstyle.edge_widths = tree.style.edge_widths

            # if user did not set opacity (assumed from 1.0) then auto-tune it
            if curstyle.edge_style["stroke-opacity"] == 1:
                curstyle.edge_style["stroke-opacity"] = 1 / len(self.treelist)

            # override some styles with user kwargs
            user = dict([
                ("_" + i, j) if isinstance(j, dict) else (i, j)
                for (i, j) in kwargs.items() 
                if (j is not None)  # and (i != "tip_labels")
            ])
            curstyle.update(user)

            # update coords based on layout
            edges = tree._coords.get_edges()
            if curstyle.layout == 'c':
                verts = tree._coords.get_radial_coords(curstyle.use_edge_lengths)
            else:
                verts = tree._coords.get_linear_coords(
                    curstyle.layout, 
                    curstyle.use_edge_lengths,
                    fixed_order,
                    None,  # TODO: add optional jitter to fixed_pos here.
                    )

            # only draw the tips for the first tree
            if tidx != 0:
                curstyle.tip_labels = False

            # check all styles
            fstyle = StyleChecker(tree, curstyle).style

            # add jitter to tips
            if jitter:
                if fstyle.layout in ['r', 'l']:
                    fstyle.ybaseline = np.random.uniform(-jitter, jitter)
                else:
                    fstyle.xbaseline = np.random.uniform(-jitter, jitter)

            # generate toyplot Mark
            mark = ToytreeMark(ntable=verts, etable=edges, **fstyle.to_dict())

            # add mark to axes
            axes.add_mark(mark)

        # get shared tree styles.
        return canvas, axes, None



    # def draw_cloud_tree(
    #     self, 
    #     axes=None, 
    #     html=False,
    #     fixed_order=True,
    #     **kwargs):
    #     """
    #     Deprecated
    #     Draw a series of trees overlapping each other in coordinate space.
    #     The order of tip_labels is fixed in cloud trees so that trees with 
    #     discordant relationships can be seen in conflict. To change the tip
    #     order use the 'fixed_order' argument in toytree.mtree() when creating
    #     the MultiTree object.

    #     Parameters:
    #         axes (toyplot.Cartesian): toyplot Cartesian axes object.
    #         html (bool): whether to return the drawing as html (default=PNG).
    #         **kwargs (dict): styling options should be input as a dictionary.
    #     """
    #     # return nothing if tree is empty
    #     if not self.treelist:
    #         print("Treelist is empty")
    #         return None, None

    #     # return nothing if tree is empty
    #     if not self.all_tips_shared:
    #         print("All trees in treelist do not share the same tips")
    #         return None, None            

    #     # make a copy of the treelist so we don't modify the original
    #     if not fixed_order:
    #         raise Exception(
    #             "fixed_order must be either True or a list with the tip order")

    #     # set fixed order on a copy of the tree list
    #     if isinstance(fixed_order, (list, tuple)):
    #         fixed_order = fixed_order
    #     elif fixed_order is True:
    #         fixed_order = self.treelist[0].get_tip_labels()
    #     else:
    #         raise Exception(
    #             "fixed_order argument must be True or a list with the tip order")
    #     treelist = [
    #         ToyTree(i, fixed_order=fixed_order) for i in self.copy().treelist
    #     ]  

    #     # give advice if user tries to enter tip_labels
    #     if kwargs.get("tip_labels"):
    #         if not isinstance(kwargs.get("tip_labels"), dict):
    #             print(TIP_LABELS_ADVICE)
    #             kwargs.pop("tip_labels")

    #     # set autorender format to png so we don't bog down notebooks
    #     try:
    #         changed_autoformat = False
    #         if not html:
    #             toyplot.config.autoformat = "png"
    #             changed_autoformat = True

    #         # dict of global cloud tree style 
    #         mstyle = deepcopy(STYLES['m'])

    #         # if trees in treelist already have some then we don't quash...
    #         mstyle.update(
    #             {i: j for (i, j) in kwargs.items() if 
    #             (j is not None) & (i != "tip_labels")}
    #         )
    #         for tree in treelist:
    #             tree.style.update(mstyle)

    #         # Send a copy of MultiTree to init Drawing object.
    #         draw = CloudTree(treelist, **kwargs)

    #         # and create drawing
    #         if kwargs.get("debug"):
    #             return draw

    #         # allow user axes, and kwargs for width, height
    #         canvas, axes, mark = draw.update(axes)
    #         return canvas, axes, mark

    #     finally:
    #         if changed_autoformat:
    #             toyplot.config.autoformat = "html"


    # # # allow ts as a shorthand for tree_style
    # # if kwargs.get("ts"):
    # #     tree_style = kwargs.get("ts")

    # # # pass a copy of this tree so that any mods to .style are not saved
    # # nself = deepcopy(self)
    # # if tree_style:
    # #     nself.style.update(TreeStyle(tree_style[0]))




TIP_LABELS_ADVICE = """
Warning: ignoring 'tip_labels' argument. 

The 'tip_labels' arg to draw_cloud_tree() should be a dictionary
mapping tip names from the contained ToyTrees to a new string value.
Example: {"a": "tip-A", "b": "tip-B", "c": tip-C"}

# get a MultiTree containing 10 trees with numbered tip names
trees = toytree.mtree([toytree.rtree.imbtree(5) for i in range(10)])

# draw a cloud tree using a set tip order and styled tip names
trees.draw_cloud_tree(
    fixed_order=['0', '1', '2', '3', '4'],
    tip_labels={i: "tip-{}".format(i) for i in trees.treelist[0].get_tip_labels()},
    )
"""