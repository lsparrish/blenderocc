def boolean_op(self, operation):
    """Boolean operations helper function
    Takes 2 selected blender objects and make BRep shapes,
    then calls an algorithm based on the passed operation string."""
    if len(bpy.context.selected_objects) != 2:
        self.report({'ERROR'}, "Select exactly 2 objects for boolean operations")
        return None
    obj1, obj2 = bpy.context.selected_objects
    shape1 = self.get_shape(obj1)
    shape2 = self.get_shape(obj2)
    BRepAlgoAPI = self.get_module('BRepAlgoAPI')
    op = getattr(BRepAlgoAPI, f'BRepAlgoAPI_{operation}')(shape1, shape2)
    op.Build()
    if op.IsDone():
        return op.Shape()
    self.report({'ERROR'}, f"Boolean {operation} operation failed")
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

@occ_operation("Rotate 90°")
def rotate_90(self):
    obj = bpy.context.active_object
    if not obj:
        return None
    shape = self.get_shape(obj)
    gp = self.get_module('gp')
    BRepBuilderAPI = self.get_module('BRepBuilderAPI')
    angle = np.pi/2
    transform = gp.gp_Trsf()
    transform.SetRotation(gp.gp_Ax1(gp.gp_Pnt(0,0,0), gp.gp_Dir(0,0,1)), angle)
    return BRepBuilderAPI.BRepBuilderAPI_Transform(shape, transform).Shape()

@occ_operation('Call AI')
def call_ai(self, message=bpy.context.scene.ai_message):
    import subprocess
    from datetime import datetime
    result = subprocess.check_output(['bash', 'ai.sh', message], text=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    self.text_name = f"ai_response_{timestamp}.txt"
    bpy.data.texts.new(self.text_name).write(result)
    def switch_to_workspace():
        bpy.context.window.workspace = bpy.data.workspaces["OCC Text"]
        bpy.app.timers.register(lambda: OCCWrapper.switch_to_text(self.text_name), first_interval=0.01)
    bpy.app.timers.register(switch_to_workspace, first_interval=0.01)
    bpy.context.window_manager.clipboard = result
    return None

@occ_operation("Open Blenderocc Files")
def open_files(self):
    filenames = ['custom_commands.py', 'blenderocc.py', 'prompt.txt', 'ai.sh', 'installer.sh']
    for filename in filenames:
        if not bpy.data.texts.get(filename):
            text = bpy.data.texts.new(filename)
            template_path = OCCEditOperator.get_template_path()
            with open(os.path.join(template_path, filename), 'r') as f:
                text.write(f.read())
        OCCUtils.switch_to_text(filename)
    return None
