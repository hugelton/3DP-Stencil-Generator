import pcbnew
import re
import datetime
import os


class StencilGenerator(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "3DP Stencil Generator"
        self.category = "Modify PCB"
        self.description = "Generate OpenSCAD file for 3D printable solder stencil with alignment holes"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), "./icon.png")

    def Run(self):
        board = pcbnew.GetBoard()
        filename = board.GetFileName()
        if not filename:
            filename = "unknown"
        else:
            filename = re.sub(r'\.[^.]*$', '', filename)

        output_filename = f"{filename}_stencil.scad"

        with open(output_filename, 'w') as f:
            f.write(self.generate_openscad(board))

        pcbnew.Refresh()
        print(f"OpenSCAD file generated: {output_filename}")

    def generate_openscad(self, board):
        scad = "// KiCad Stencil Generator\n"
        scad += f"// Generated on {datetime.datetime.now()}\n\n"

        scad += "// Parameters (adjust as needed)\n"
        scad += "stencil_thickness = 0.2;  // mm (Thickness of the stencil)\n"
        scad += "frame_height = 2.0;       // mm (Height of the frame)\n"
        scad += "pcb_thickness = 1.6;      // mm (Thickness of the PCB)\n"
        scad += "alignment_pin_diameter = 3.0;  // mm (Diameter of alignment holes)\n"
        scad += "\n"
        scad += "// Feature toggle\n"
        scad += "enable_alignment_holes = true;\n"
        scad += "\n"
        scad += "$fs = 0.1;  // Set minimum facet size for curves\n"
        scad += "$fa = 5;    // Set minimum angle for facets\n\n"

        scad += self.generate_modules(board)

        scad += "union(){\n"
        scad += "stencil();\n"
        scad += "        if (enable_alignment_holes) alignment_holes();\n}"

        return scad

    def generate_modules(self, board):
        scad = "module frame() {\n"
        scad += self.generate_frame(board)
        scad += "}\n\n"

        scad += "module pcb_outline() {\n"
        scad += self.generate_pcb_outline(board)
        scad += "}\n\n"

        scad += "module pads() {\n"
        scad += self.generate_pads(board)
        scad += "}\n\n"

        scad += "module alignment_holes() {\n"
        scad += self.generate_alignment_holes(board)
        scad += "}\n\n"

        scad += "module stencil() {\n"
        scad += "    difference() {\n"
        scad += "        frame();\n"
        scad += "        translate([0, 0, frame_height - pcb_thickness]) {\n"
        scad += "            linear_extrude(height=pcb_thickness + 0.01) {\n"
        scad += "                pcb_outline();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "        translate([0, 0, - stencil_thickness]) {\n"
        scad += "            linear_extrude(height=frame_height + stencil_thickness) {\n"
        scad += "                pads();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "    }\n"
        scad += "}\n\n"

        return scad

    def generate_frame(self, board):
        frame_rect = self.find_shape_on_layer(board, pcbnew.User_8)
        if not frame_rect:
            return "    // No frame found on User.8 layer\n"

        scad = f"    linear_extrude(height=frame_height) {{\n"
        scad += f"        square([{self.mm(frame_rect[2])}, {self.mm(frame_rect[3])}], center=true);\n"
        scad += "    }\n"
        return scad

    def generate_pcb_outline(self, board):
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if not pcb_rect:
            return "    // No PCB outline found on User.9 layer\n"

        scad = f"    square([{self.mm(pcb_rect[2])}, {self.mm(pcb_rect[3])}], center=true);\n"
        return scad

    def generate_pads(self, board):
        scad = ""
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if not pcb_rect:
            return "    // No PCB outline found on User.9 layer\n"

        center_x = pcb_rect[0] + pcb_rect[2]/2
        center_y = pcb_rect[1] + pcb_rect[3]/2

        for module in board.GetFootprints():
            for pad in module.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    pos = pad.GetPosition()
                    size = pad.GetSize()
                    angle = pad.GetOrientation().AsDegrees()
                    scad += f"    translate([{self.mm(pos.x - center_x)}, {self.mm(pos.y - center_y)}]) "
                    scad += f"rotate([0, 0, {angle}]) "
                    scad += f"square([{self.mm(size.x)}, {self.mm(size.y)}], center=true);\n"
        return scad

    def generate_alignment_holes(self, board):
        alignment_holes = self.find_circles_on_layer(board, pcbnew.User_7)
        if not alignment_holes:
            return "    // No alignment holes found on User.7 layer\n"

        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if not pcb_rect:
            return "    // No PCB outline found on User.9 layer\n"

        center_x = pcb_rect[0] + pcb_rect[2]/2
        center_y = pcb_rect[1] + pcb_rect[3]/2

        scad = ""
        for hole in alignment_holes:
            x = self.mm(hole[0] - center_x)
            y = self.mm(hole[1] - center_y)
            scad += f"    translate([{x}, {y}, -0.005]) "
            scad += f"cylinder(h=frame_height + 0.01, d=alignment_pin_diameter, center=false);\n"
        return scad

    def find_shape_on_layer(self, board, layer):
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_RECT and
                    drawing.GetLayer() == layer):
                return (drawing.GetStart().x, drawing.GetStart().y,
                        drawing.GetEnd().x - drawing.GetStart().x,
                        drawing.GetEnd().y - drawing.GetStart().y)
        return None

    def find_circles_on_layer(self, board, layer):
        circles = []
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_CIRCLE and
                    drawing.GetLayer() == layer):
                center = drawing.GetCenter()
                circles.append((center.x, center.y))
        return circles

    def mm(self, nm):
        return nm / 1e6


StencilGenerator().register()
