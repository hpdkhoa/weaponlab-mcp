"""Blueprint Lab: a real gun's visual copy from its public sources (docs/DIGITIZE.md).

    sources   register the files (manuals, patents, photos) with their licenses; scan their pages; render a page
    specs     the facts in the data tables (lengths, weights), each with its page and quote
    figures   a figure cut from a page, turned upright, scaled by a known length, framed in gun space
    trace     outlines from a figure: the whole silhouette, a closed region, or a rough outline snapped to the ink
    plan      the blueprint: parts (shape, holes, motion, finish, sources), marks
    check     the blueprint against its contract, its figures (outline overlap) and its facts (sums)
    build     the blueprint as a model in Blender (one object a part) and its parts map for Gun Kit

Every file of a gun lives in <work>/digitize/<gun>/. Claude picks the figures and names the parts; the tools take
every number."""
