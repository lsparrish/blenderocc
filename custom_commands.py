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

@occ_operation("Export SVG")
def export_svg(self):
    obj = bpy.context.active_object
    if not obj:
        return None
    mesh = obj.data.copy()
    mesh.transform(obj.matrix_world)
    def iso_project(v):
        x,y,z = v.co
        a, b = 0.866025, 0.5
        return (x * a - y * a, x * b + y * b - z)
    points = [iso_project(v) for v in mesh.vertices]
    bounds = {'x': [p[0] for p in points], 'y': [p[1] for p in points]}
    margin = max(max(b) - min(b) for b in bounds.values()) * 0.1
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min(bounds["x"])-margin} {min(bounds["y"])-margin} {max(bounds["x"])-min(bounds["x"])+2*margin} {max(bounds["y"])-min(bounds["y"])+2*margin}">']
    for face in sorted(mesh.polygons, key=lambda f: f.normal.z):
        path = [f"{points[i][0]},{points[i][1]}" for i in face.vertices]
        color = ["#808080","#a0a0a0","#d0d0d0"][int((face.normal.z+1)*1.499)]
        svg.append(f'<path d="M {path[0]} L {" L ".join(path[1:])} Z" fill="{color}" stroke="none"/>')
    svg.append('</svg>')
    bpy.context.window_manager.clipboard = '\n'.join(svg)
    bpy.data.meshes.remove(mesh)
    return None
