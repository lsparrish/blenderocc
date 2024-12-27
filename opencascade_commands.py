def boolean_op(self, operation):
    """Boolean operations helper function
    Takes 2 selected blender objects and make BRep shapes,
    then calls an algorithm based on the passed operation string."""
    if len(bpy.context.selected_objects) != 2:
        return None
    obj1, obj2 = bpy.context.selected_objects
    shape1 = self.get_shape(obj1)
    shape2 = self.get_shape(obj2)

    BRepAlgoAPI = self.get_module('BRepAlgoAPI')
    op = getattr(BRepAlgoAPI, f'BRepAlgoAPI_{operation}')(shape1, shape2)
    op.Build()
    if op.IsDone():
        return op.Shape()
    return None
OCCWrapper.boolean_op = boolean_op

@occ_operation("Create Cube")
def make_cube(self, size=1.0):
    BRepPrimAPI = self.get_module('BRepPrimAPI')
    return BRepPrimAPI.BRepPrimAPI_MakeBox(size, size, size).Shape()

@occ_operation("Boolean Union")
def boolean_union(self):
    return self.boolean_op('Fuse')

@occ_operation("Boolean Intersection")
def boolean_intersection(self):
    return self.boolean_op('Common')

@occ_operation("Boolean Difference")
def boolean_difference(self):
    return self.boolean_op('Cut')

@occ_operation("Reload Addon")
def reload_plugin(self, name='blenderocc'):
    import addon_utils
    addon_utils.disable(name)
    addon_utils.enable(name)
    print(name, "addon reloaded")
