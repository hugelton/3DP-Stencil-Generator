# 3DP Stencil Generator for KiCad
# Original Author: Leo Kuroshita (Hugelton Instruments)
# License: MIT
# Repository: https://github.com/hugelton/3DP-Stencil-Generator

import pcbnew
import re
import datetime
import os
import configparser


# === Global configuration ===
BUILD = "127"            # Build number
workDir = "stencil"      # Working folder name
frontCopperPads = True # Generate front copper pads
backCopperPads = False # Generate back copper pads
copperSelection = 0     # 0 = front, 1 = back
minGabBetweenPads = 0.20    # Minimum mask width (mm) between pads
minPadSize = 0.40      # Minimum pad size (mm) after shrinking
narrowPadThreshold = 1.0  # Threshold for narrow pad optimization (mm)
pcbClearence = 0.15      # PCB clearance (mm) - moves outline outward from Edge.Cuts

import wx

def loadConfigFromIni(projectDir):
    """Load configuration from 3dpStencil.ini file"""
    global minGabBetweenPads, minPadSize, pcbClearence, narrowPadThreshold
    
    config_file = os.path.join(projectDir, workDir, "3dpStencil.ini")
    
    if not os.path.exists(config_file):
        return  # Use default values
    
    try:
        config = configparser.ConfigParser()
        config.read(config_file, encoding='utf-8')
        
        if 'StencilSettings' in config:
            settings = config['StencilSettings']
            
            # Load values with validation
            if 'minGabBetweenPads' in settings:
                value = float(settings['minGabBetweenPads'])
                if 0.01 <= value <= 5.0:  # Reasonable range
                    minGabBetweenPads = value
            
            if 'minPadSize' in settings:
                value = float(settings['minPadSize'])
                if 0.01 <= value <= 10.0:  # Reasonable range
                    minPadSize = value
            
            if 'pcbCearance' in settings:
                value = float(settings['pcbCearance'])
                if 0.0 <= value <= 2.0:  # Reasonable range
                    pcbClearence = value
            
            if 'narrowPadThreshold' in settings:
                value = float(settings['narrowPadThreshold'])
                if 0.1 <= value <= 5.0:  # Reasonable range
                    narrowPadThreshold = value
        
        # make sure minPadSize is not smaller than narrowPadThreshold
        if minPadSize < narrowPadThreshold:
            minPadSize = narrowPadThreshold
                    
    except Exception as e:
        # If any error occurs, just use default values
        print(f"Warning: Could not load config from {config_file}: {e}")


def saveConfigToIni(projectDir, maskWidth, padSize, clearance, narrowThreshold):
    """Save configuration to 3dpStencil.ini file"""
    config_dir = os.path.join(projectDir, workDir)
    config_file = os.path.join(config_dir, "3dpStencil.ini")
    
    try:
        # Ensure directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Create config
        config = configparser.ConfigParser()
        config['StencilSettings'] = {
            'minGabBetweenPads': str(maskWidth),
            'minPadSize': str(padSize),
            'pcbCearance': str(clearance),
            'narrowPadThreshold': str(narrowThreshold)
        }
        
        # Write config file
        with open(config_file, 'w', encoding='utf-8') as f:
            config.write(f)
            
    except Exception as e:
        # Don't crash if we can't save config
        print(f"Warning: Could not save config to {config_file}: {e}")


class StencilParametersDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Stencil Generator Parameters")
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.copper_side_rb = wx.RadioBox(
            self, label="Copper side", choices=["Front", "Back"], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.copper_side_rb.SetSelection(0 if frontCopperPads else 1)
        sizer.Add(self.copper_side_rb, 0, wx.ALL, 5)
        
        # Minimum gab between pads width
        sizer.Add(wx.StaticText(self, label="Minimum Gab Between Pads (mm):"), 0, wx.ALL, 5)
        self.maskWidth_ctrl = wx.TextCtrl(self, value=str(minGabBetweenPads))
        sizer.Add(self.maskWidth_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # Minimum pad size
        sizer.Add(wx.StaticText(self, label="Minimum pad size (mm):"), 0, wx.ALL, 5)
        self.padSize_ctrl = wx.TextCtrl(self, value=str(minPadSize))
        sizer.Add(self.padSize_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # PCB clearance
        sizer.Add(wx.StaticText(self, label="PCB clearance (mm):"), 0, wx.ALL, 5)
        self.clearance_ctrl = wx.TextCtrl(self, value=str(pcbClearence))
        sizer.Add(self.clearance_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # Narrow pad threshold
        sizer.Add(wx.StaticText(self, label="Narrow Pad Threshold (mm):"), 0, wx.ALL, 5)
        self.narrowThreshold_ctrl = wx.TextCtrl(self, value=str(narrowPadThreshold))
        sizer.Add(self.narrowThreshold_ctrl, 0, wx.ALL|wx.EXPAND, 5)
        
        # OK and Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL|wx.CENTER, 5)
        
        self.SetSizer(sizer)
        self.Fit()
    
    def getValues(self):
        """Return the values from the dialog"""
        try:
            copperSelection = self.copper_side_rb.GetSelection()
            maskWidth = float(self.maskWidth_ctrl.GetValue())
            padSize = float(self.padSize_ctrl.GetValue())
            clearance = float(self.clearance_ctrl.GetValue())
            narrowThreshold = float(self.narrowThreshold_ctrl.GetValue())
            
            # NIEUWE VALIDATIE: Zorg dat minPadSize nooit kleiner is dan narrowPadThreshold
            if padSize < narrowThreshold:
                wx.MessageBox(f"Minimum pad size ({padSize}) cannot be smaller than narrow pad threshold ({narrowThreshold})!", "Validation Error")
                return None
            
            return {
                'copperSelection': copperSelection,
                'frontCopperPads': copperSelection == 0,
                'backCopperPads': copperSelection == 1,
                'minGabBetweenPads': maskWidth,
                'minPadSize': padSize,
                'pcbCearance': clearance,
                'narrowPadThreshold': narrowThreshold
            }
        except ValueError:
            wx.MessageBox("Please enter valid numbers for all numeric fields!", "Error")
            return None

class StencilGenerator(pcbnew.ActionPlugin):
    def get_debug_log_function(self):
        """Get unified debug logging function"""
        try:
            board = pcbnew.GetBoard()
            projectFile = board.GetFileName()
            projectDir = os.path.dirname(projectFile)
            output_dir = os.path.join(projectDir, workDir)
            log_file = os.path.join(output_dir, "kicad_stencilgen_debug.log")
            
            def debug_log(msg):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now().strftime('%H:%M:%S')} - {msg}\n")
            
            return debug_log
        except:
            return lambda msg: print(f"DEBUG: {msg}")
    
    def defaults(self):
        self.name = "3dp Stencil Generator"
        self.category = "Modify PCB"
        self.description = "Generate OpenSCAD file for 3D printable solder stencil with alignment holes"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), "./icon.png")

    def showParametersDialog(self):
        app = wx.App.Get()
        if not app:
            app = wx.App()
        dlg = StencilParametersDialog(None)
        if dlg.ShowModal() == wx.ID_OK:
            values = dlg.getValues()
            if values:
                global frontCopperPads, backCopperPads, minGabBetweenPads, minPadSize, pcbClearence, copperSelection, narrowPadThreshold
                copperSelection = values['copperSelection']
                frontCopperPads = values['frontCopperPads']
                backCopperPads = values['backCopperPads']
                minGabBetweenPads = values['minGabBetweenPads']
                minPadSize = values['minPadSize']
                narrowPadThreshold = values['narrowPadThreshold']
                pcbClearence = values['pcbCearance']
                dlg.Destroy()
                return True
        dlg.Destroy()
        return False


    def Run(self):
        try:
            board = pcbnew.GetBoard()
            projectFile = board.GetFileName()

            if not projectFile:
                raise RuntimeError("No board file loaded")

            projectDir = os.path.dirname(projectFile)
            output_dir = os.path.join(projectDir, workDir)
            os.makedirs(output_dir, exist_ok=True)

            log_file = os.path.join(output_dir, "kicad_stencilgen_debug.log")

            def log(msg):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")

            log(f"===== Plugin started - BUILD {BUILD} =====")
            log(f"Project directory: {projectDir}")

            # Load configuration from INI file
            loadConfigFromIni(projectDir)
            log(f"Config loaded - maskWidth: {minGabBetweenPads}, padSize: {minPadSize}, narrowPadThreshold: {narrowPadThreshold}, clearance: {pcbClearence}")

            # Show parameter dialog
            log("Showing parameters dialog")
            if not self.showParametersDialog():
                log("Parameters dialog cancelled, exiting")
                return  # User cancelled, exit

            # Save configuration to INI file
            saveConfigToIni(projectDir, minGabBetweenPads, minPadSize, pcbClearence, narrowPadThreshold)
            log("Configuration saved to INI file")

            baseFilename = re.sub(r'\.[^.]*$', '', os.path.basename(projectFile))
            # Gebruik nu copperSelection voor de bestandsnaam
            if copperSelection == 0:
                sideStr = "F"
            elif copperSelection == 1:
                sideStr = "B"
            else:
                sideStr = ""
            outputFilename = os.path.join(output_dir, f"{baseFilename}_stencil_{sideStr}.scad")

            log(f"Output SCAD file: {outputFilename}")
            with open(outputFilename, 'w', encoding='utf-8') as f:
                f.write(self.generateOpenscad(board))
                log(f"SCAD file written: {outputFilename}")

            pcbnew.Refresh()
            print(f"OpenSCAD file generated: {outputFilename}")
            log("Script completed successfully")
            
            # Open the stencil folder in file explorer
            import subprocess
            import platform
            system = platform.system()
            try:
                if system == 'Darwin':  # macOS
                    subprocess.run(['open', output_dir])
                elif system == 'Windows':
                    subprocess.run(['explorer', output_dir])
                elif system == 'Linux':
                    subprocess.run(['xdg-open', output_dir])
                log(f"Opened stencil folder: {output_dir}")
            except Exception as e:
                log(f"Could not open folder automatically: {e}")

        except Exception as e:
            msg = f"ERROR in Run(): {repr(e)}"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
            except:
                print("Error writing to log file.")
            print(msg)


    def generateOpenscad(self, board):
        # Haal bestandsnaam op
        projectFile = board.GetFileName()
        baseFilename = re.sub(r'\.[^.]*$', '', os.path.basename(projectFile))
        if copperSelection == 0:
            sideStr = "F"
        elif copperSelection == 1:
            sideStr = "B"
        else:
            sideStr = ""
        scadFilename = f"{baseFilename}_stencil_{sideStr}.scad"
        
        scad = "// KiCad Stencil Generator\n"
        scad += f"// Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        scad += f"// File: {scadFilename}\n"
        scad += f"// minGabBetweenPads: {minGabBetweenPads} mm\n"
        scad += f"// minPadSize: {minPadSize} mm\n"
        scad += f"// pcbClearence: {pcbClearence} mm\n\n"

        scad += "// Parameters (adjust as needed)\n"
        scad += "stencilThickness = 0.2;  // mm (Thickness of the stencil)\n"
        scad += "frameHeight = 2.0;       // mm (Height of the frame)\n"
        scad += "pcbThickness = 1.6;      // mm (Thickness of the PCB)\n"
        scad += "alignment_pin_diameter = 3.0;  // mm (Diameter of alignment holes)\n"
        scad += "\n"
        scad += "// Feature toggle\n"
        scad += "enable_alignmentHoles = true;\n"
        scad += "\n"
        scad += "$fs = 0.1;  // Set minimum facet size for curves\n"
        scad += "$fa = 5;    // Set minimum angle for facets\n\n"

        scad += self.generate_modules(board)

        scad += "difference(){\n"
        scad += "stencil();\n"
        scad += "        if (enable_alignmentHoles) alignmentHoles();\n}"

        return scad

    def generate_modules(self, board):
        scad = "module frame() {\n"
        scad += self.generateFrame(board)
        scad += "}\n\n"

        scad += "module pcbOutline() {\n"
        scad += self.generatePcbOutline(board)
        scad += "}\n\n"

        scad += "module pads() {\n"
        scad += self.generatePads(board)
        scad += "}\n\n"

        scad += "module alignmentHoles() {\n"
        scad += self.generateAlignmentHoles(board)
        scad += "}\n\n"

        scad += "module stencil() {\n"
        scad += "    difference() {\n"
        scad += "        frame();\n"
        scad += "        translate([0, 0, frameHeight - pcbThickness]) {\n"
        scad += "            linear_extrude(height=pcbThickness + 0.01) {\n"
        scad += "                pcbOutline();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "        translate([0, 0, - stencilThickness]) {\n"
        scad += "            linear_extrude(height=frameHeight + stencilThickness) {\n"
        scad += "                pads();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "    }\n"
        scad += "}\n\n"

        return scad

    def calculatePcbBounds(self, board):
        """Calculate PCB bounds for frame generation"""
        # Try User.4 first (preferred method)
        pcbRect = self.findShapeOnLayer(board, pcbnew.User_4)
        if pcbRect:
            # User.4 rectangle found - use its bounds
            centerX = pcbRect[0] + pcbRect[2]/2
            centerY = pcbRect[1] + pcbRect[3]/2
            width = self.mm(pcbRect[2])
            height = self.mm(pcbRect[3])
            return {
                'centerX': centerX,
                'centerY': centerY,
                'width': width,
                'height': height
            }
        
        # Fallback: analyze Edge.Cuts to determine bounds
        # Get all Edge.Cuts elements to calculate bounding box
        minX = float('inf')
        maxX = float('-inf')
        minY = float('inf')
        maxY = float('-inf')
        
        foundEdgeCuts = False
        
        for drawing in board.GetDrawings():
            if drawing.GetLayer() == pcbnew.Edge_Cuts and isinstance(drawing, pcbnew.PCB_SHAPE):
                foundEdgeCuts = True
                shapeType = drawing.GetShape()
                
                if shapeType == pcbnew.SHAPE_T_SEGMENT:
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    minX = min(minX, start.x, end.x)
                    maxX = max(maxX, start.x, end.x)
                    minY = min(minY, start.y, end.y)
                    maxY = max(maxY, start.y, end.y)
                    
                elif shapeType == pcbnew.SHAPE_T_CIRCLE:
                    center = drawing.GetCenter()
                    radius = drawing.GetRadius()
                    minX = min(minX, center.x - radius)
                    maxX = max(maxX, center.x + radius)
                    minY = min(minY, center.y - radius)
                    maxY = max(maxY, center.y + radius)
                    
                elif shapeType == pcbnew.SHAPE_T_RECT:
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    minX = min(minX, start.x, end.x)
                    maxX = max(maxX, start.x, end.x)
                    minY = min(minY, start.y, end.y)
                    maxY = max(maxY, start.y, end.y)
                    
                elif shapeType == pcbnew.SHAPE_T_ARC:
                    # For arcs, include start, end, and center points as approximation
                    center = drawing.GetCenter()
                    start = drawing.GetStart()
                    end = drawing.GetEnd()
                    minX = min(minX, center.x, start.x, end.x)
                    maxX = max(maxX, center.x, start.x, end.x)
                    minY = min(minY, center.y, start.y, end.y)
                    maxY = max(maxY, center.y, start.y, end.y)
        
        if foundEdgeCuts and minX != float('inf'):
            # Calculate bounds from Edge.Cuts
            centerX = (minX + maxX) / 2
            centerY = (minY + maxY) / 2
            width = self.mm(maxX - minX)
            height = self.mm(maxY - minY)
            return {
                'centerX': centerX,
                'centerY': centerY,
                'width': width,
                'height': height
            }
        
        # Ultimate fallback: use board bounding box
        bbox = board.GetBoundingBox()
        centerX = bbox.GetCenter().x
        centerY = bbox.GetCenter().y
        width = self.mm(bbox.GetWidth())
        height = self.mm(bbox.GetHeight())
        
        return {
            'centerX': centerX,
            'centerY': centerY,
            'width': width,
            'height': height
        }

    def generateFrame(self, board):
        # First, try to find existing rectangle on User.3 layer
        frameRect = self.findShapeOnLayer(board, pcbnew.User_3)
        
        if frameRect:
            # User.3 rectangle found - use existing logic
            scad = f"    linear_extrude(height=frameHeight) {{\n"
            scad += f"        square([{self.mm(frameRect[2])}, {self.mm(frameRect[3])}], center=true);\n"
            scad += "    }\n"
            return scad
    
        # User.3 rectangle not found - auto-calculate frame
        pcbBounds = self.calculatePcbBounds(board)
        
        # Add 5mm margin on all sides (10mm total to width and height)
        frameMargin = 5.0  # mm
        frameWidth = pcbBounds['width'] + (2 * frameMargin)
        frameHeight = pcbBounds['height'] + (2 * frameMargin)
        
        scad = f"    // Auto-calculated frame (PCB + {frameMargin}mm margin)\n"
        scad += f"    linear_extrude(height=frameHeight) {{\n"
        scad += f"        square([{frameWidth}, {frameHeight}], center=true);\n"
        scad += "    }\n"
        
        return scad
    
    def connectLineSegments(self, segments):
        """Try to connect line segments into a closed polygon"""
        if not segments:
            return []
        
        # Start with the first segment
        polygon = list(segments[0])
        usedSegments = {0}
        
        tolerance = 0.01  # mm tolerance for connecting points
        
        while len(usedSegments) < len(segments):
            lastPoint = polygon[-1]
            foundConnection = False
            
            # Look for a segment that connects to the last point
            for i, segment in enumerate(segments):
                if i in usedSegments:
                    continue
                    
                start, end = segment
                
                # Check if segment start connects to last point
                if self.pointsClose(lastPoint, start, tolerance):
                    polygon.append(end)
                    usedSegments.add(i)
                    foundConnection = True
                    break
                # Check if segment end connects to last point
                elif self.pointsClose(lastPoint, end, tolerance):
                    polygon.append(start)
                    usedSegments.add(i)
                    foundConnection = True
                    break
            
            if not foundConnection:
                # Can't connect more segments
                break
        
        # Check if we have a closed polygon (last point connects to first)
        if len(polygon) > 2 and self.pointsClose(polygon[-1], polygon[0], tolerance):
            polygon.pop()  # Remove duplicate closing point
            return polygon
        
        # If not closed or too few segments used, return empty
        if len(usedSegments) < len(segments) * 0.8:  # At least 80% of segments should be used
            return []
        
        return polygon

    def pointsClose(self, p1, p2, tolerance):
        """Check if two points are within tolerance distance"""
        return abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance

    def mm(self, nm):
        return nm / 1e6

    def generatePcbOutlineFromEdgeCuts(self, board):
      """Generate PCB outline from Edge.Cuts layer as a single polygon or union of shapes"""
      log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
      log("=== Starting Edge.Cuts analysis ===")

      pcbRect = self.findShapeOnLayer(board, pcbnew.User_4)
      if pcbRect:
          centerX = pcbRect[0] + pcbRect[2]/2
          centerY = pcbRect[1] + pcbRect[3]/2
          log(f"Using User.4 center: ({self.mm(centerX)}, {self.mm(centerY)}) mm")
      else:
          bbox = board.GetBoundingBox()
          centerX = bbox.GetCenter().x
          centerY = bbox.GetCenter().y
          log(f"Using board bbox center: ({self.mm(centerX)}, {self.mm(centerY)}) mm")

      shapes = []
      lineSegments = []

      for drawing in board.GetDrawings():
          if drawing.GetLayer() == pcbnew.Edge_Cuts and isinstance(drawing, pcbnew.PCB_SHAPE):
              shapeType = drawing.GetShape()

              if shapeType == pcbnew.SHAPE_T_SEGMENT:
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - centerX), self.mm(start.y - centerY)
                  x2, y2 = self.mm(end.x - centerX), self.mm(end.y - centerY)
                  lineSegments.append([(x1, y1), (x2, y2)])

              elif shapeType == pcbnew.SHAPE_T_CIRCLE:
                  centerCircle = drawing.GetCenter()
                  radius = drawing.GetRadius()
                  cx, cy = self.mm(centerCircle.x - centerX), self.mm(centerCircle.y - centerY)
                  # Spiegel X-coördinaat voor Back kant (net zoals bij pads)
                  if backCopperPads:  # of copperSelection == 1
                      cx = -cx
                  r = self.mm(radius) + pcbClearence
                  shapes.append(f"translate([{cx}, {cy}]) circle(r={r})")

              elif shapeType == pcbnew.SHAPE_T_RECT:
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - centerX), self.mm(start.y - centerY)
                  x2, y2 = self.mm(end.x - centerX), self.mm(end.y - centerY)
                  w, h = abs(x2 - x1) + 2 * pcbClearence, abs(y2 - y1) + 2 * pcbClearence
                  cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                  shapes.append(f"translate([{cx}, {cy}]) square([{w}, {h}], center=true)")

              elif shapeType == pcbnew.SHAPE_T_ARC:
                  center_arc = drawing.GetCenter()
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  import math
                  cx, cy = self.mm(center_arc.x - centerX), self.mm(center_arc.y - centerY)
                  sx, sy = self.mm(start.x - centerX), self.mm(start.y - centerY)
                  ex, ey = self.mm(end.x - centerX), self.mm(end.y - centerY)
                  radius = math.sqrt((sx - cx)**2 + (sy - cy)**2)
                  startAngle = math.atan2(sy - cy, sx - cx)
                  endAngle = math.atan2(ey - cy, ex - cx)
                  arcPoints = []
                  num_segments = max(8, int(abs(endAngle - startAngle) * 180 / math.pi / 10))
                  if endAngle < startAngle:
                      endAngle += 2 * math.pi
                  for i in range(num_segments + 1):
                      angle = startAngle + (endAngle - startAngle) * i / num_segments
                      x = cx + radius * math.cos(angle)
                      y = cy + radius * math.sin(angle)
                      arcPoints.append((x, y))
                  for i in range(len(arcPoints) - 1):
                      lineSegments.append([arcPoints[i], arcPoints[i + 1]])

      scad = ""
      if lineSegments:
          polygonPoints = self.connectLineSegments(lineSegments)
          if polygonPoints:
              # Spiegel X-coordinaat en reverse de volgorde voor Back
              if backCopperPads:
                  polygonPoints = [(-x, y) for x, y in polygonPoints][::-1]
              pointsStr = ",".join([f"[{x},{y}]" for x, y in polygonPoints])
              scad += f"    offset(r={pcbClearence}) polygon(points=[{pointsStr}]);\n"
          else:
              for segment in lineSegments:
                  (x1, y1), (x2, y2) = segment
                  if backCopperPads:
                      x1 = -x1
                      x2 = -x2
                  length = ((x2-x1)**2 + (y2-y1)**2)**0.5
                  if length > 0.001:
                      import math
                      angle = math.atan2(y2-y1, x2-x1) * 180 / math.pi
                      cx, cy = (x1+x2)/2, (y1+y2)/2
                      lineWidth = 0.1 + 2 * pcbClearence
                      shapes.append(f"translate([{cx}, {cy}]) rotate([0, 0, {angle}]) square([{length}, {lineWidth}], center=true)")

      if shapes:
          if scad:
              scad = f"    union() {{\n{scad}"
              for shape in shapes:
                  scad += f"        {shape};\n"
              scad += "    }\n"
          else:
              if len(shapes) == 1:
                  scad = f"    {shapes[0]};\n"
              else:
                  scad = "    union() {\n"
                  for shape in shapes:
                      scad += f"        {shape};\n"
                  scad += "    }\n"

      if not scad:
          bbox = board.GetBoundingBox()
          w = self.mm(bbox.GetWidth()) + 2 * pcbClearence
          h = self.mm(bbox.GetHeight()) + 2 * pcbClearence
          scad = f"    square([{w}, {h}], center=true);\n"

      log("=== Edge.Cuts analysis complete ===")
      return scad

    def generatePcbOutline(self, board):
        log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
        self.debugAllLayers(board)
        pcbRect = self.findShapeOnLayer(board, pcbnew.User_4)
        if pcbRect:
            log("Using User.4 rectangle for PCB outline")
            scad = f"    square([{self.mm(pcbRect[2])}, {self.mm(pcbRect[3])}], center=true);\n"
            return scad
        else:
            log("No User.4 rectangle found, falling back to Edge.Cuts")
            return self.generatePcbOutlineFromEdgeCuts(board)


    def getPadBounds(self, pad_info):
        """Get the bounding box of a pad considering its rotation"""
        import math
        
        angleRad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Calculate rotated corner positions
        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h)
        ]
        
        rotated_corners = []
        for x, y in corners:
            rx = x * math.cos(angleRad) - y * math.sin(angleRad)
            ry = x * math.sin(angleRad) + y * math.cos(angleRad)
            rotated_corners.append((rx + pad_info['x'], ry + pad_info['y']))
        
        minX = min(corner[0] for corner in rotated_corners)
        maxX = max(corner[0] for corner in rotated_corners)
        minY = min(corner[1] for corner in rotated_corners)
        maxY = max(corner[1] for corner in rotated_corners)
        
        return {
            'minX': minX,
            'maxX': maxX,
            'minY': minY,
            'maxY': maxY,
            'width': maxX - minX,
            'height': maxY - minY
        }

    def findClosePads(self, current_pad, allPads, currentIndex, searchRadius):
        """Find pads within searchRadius of the current pad"""
        import math
        
        close_pads = []
        currentX = current_pad['x']
        currentY = current_pad['y']
        
        for i, pad in enumerate(allPads):
            if i == currentIndex:
                continue
                
            dx = pad['x'] - currentX
            dy = pad['y'] - currentY
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance <= searchRadius:
                close_pads.append(pad)
        
        return close_pads

        
    def optimizeNarrowPads(self, padsInfo, groupShrinkFactors):
        """Optimize narrow pads to maximize their dimensions while respecting constraints"""
        import math
        
        debug_log = self.get_debug_log_function()
        
        optimizedFactors = groupShrinkFactors.copy()
        narrowPadsFound = 0
        actuallyOptimized = 0
        cappedAtMinPadSize = 0
        
        # Only log header if we find narrow pads
        headerLogged = False
        
        for i, pad_info in enumerate(padsInfo):
            # Check if this pad has any dimension below threshold
            minDimension = min(pad_info['width'], pad_info['height'])
            isNarrow = minDimension < narrowPadThreshold
            
            if isNarrow:
                narrowPadsFound += 1
                
                # Start with no shrinking (factor 1.0)
                currentFactors = optimizedFactors.get(i, {'width': 1.0, 'height': 1.0})
                originalFactors = currentFactors.copy()
                wasOptimized = False
                wasCapped = False
                
                # Try to optimize width if it's narrow
                if pad_info['width'] < narrowPadThreshold:
                    maxPossibleWidth = self.calculateMaxPadDimension(pad_info, padsInfo, i, 'width')
                    if maxPossibleWidth > pad_info['width']:
                        newWidthFactor = maxPossibleWidth / pad_info['width']
                        currentFactors['width'] = newWidthFactor
                        wasOptimized = True
                        
                        # Check if we were capped at minPadSize
                        if maxPossibleWidth >= minPadSize:
                            wasCapped = True
                
                # Try to optimize height if it's narrow
                if pad_info['height'] < narrowPadThreshold:
                    maxPossibleHeight = self.calculateMaxPadDimension(pad_info, padsInfo, i, 'height')
                    if maxPossibleHeight > pad_info['height']:
                        newHeightFactor = maxPossibleHeight / pad_info['height']
                        currentFactors['height'] = newHeightFactor
                        wasOptimized = True
                        
                        # Check if we were capped at minPadSize
                        if maxPossibleHeight >= minPadSize:
                            wasCapped = True
                
                # Only log if pad was actually optimized
                if wasOptimized:
                    if not headerLogged:
                        debug_log("=== NARROW PAD OPTIMIZATION ===")
                        debug_log(f"narrowPadThreshold: {narrowPadThreshold} mm")
                        debug_log(f"minPadSize (max limit): {minPadSize} mm")
                        debug_log(f"minGabBetweenPads: {minGabBetweenPads} mm")
                        headerLogged = True
                    
                    actuallyOptimized += 1
                    if wasCapped:
                        cappedAtMinPadSize += 1
                        
                    optimizedFactors[i] = currentFactors
                    
                    # Calculate final dimensions
                    finalWidth = pad_info['width'] * currentFactors['width']
                    finalHeight = pad_info['height'] * currentFactors['height']
                    
                    debug_log(f"Pad {i}: pos=({pad_info['x']:.3f}, {pad_info['y']:.3f})")
                    debug_log(f"  OPTIMIZED: {pad_info['width']:.3f}x{pad_info['height']:.3f} -> {finalWidth:.3f}x{finalHeight:.3f}")
                    debug_log(f"  Factors: width={currentFactors['width']:.3f}, height={currentFactors['height']:.3f}")
                    if wasCapped:
                        debug_log(f"  NOTE: Capped at minPadSize limit ({minPadSize} mm)")
        
        if headerLogged:
            debug_log(f"=== OPTIMIZATION SUMMARY ===")
            debug_log(f"Narrow pads found: {narrowPadsFound}, Actually optimized: {actuallyOptimized}")
            if cappedAtMinPadSize > 0:
                debug_log(f"Pads capped at minPadSize limit: {cappedAtMinPadSize}")
            debug_log("")  # Empty line for readability
        
        return optimizedFactors

        
    def calculateMaxPadDimension(self, targetPad, allPads, targetIndex, dimension):
        """
        Calculate maximum possible dimension for a narrow pad while respecting minGabBetweenPads.
        
        This function implements intelligent directional expansion:
        - If space available in both directions: expand symmetrically up to minPadSize
        - If space only in one direction: expand toward that direction up to minPadSize  
        - If no space in either direction: keep original size
        - Always respect minGabBetweenPads constraints with neighboring pads
        
        Args:
            targetPad: Dictionary with pad info (x, y, width, height, angle)
            allPads: List of all pad dictionaries
            targetIndex: Index of target pad in allPads list
            dimension: 'width' or 'height' - which dimension to optimize
            
        Returns:
            float: Maximum safe dimension size (capped at minPadSize)
        """
        import math
        
        debug_log = self.get_debug_log_function()
        
        # Get original dimension value
        originalDimension = targetPad[dimension]
        
        # Target size is minPadSize for narrow pad optimization
        targetSize = minPadSize
        
        # If already at or above target, no optimization needed
        if originalDimension >= targetSize:
            return originalDimension
        
        # Calculate how much expansion is needed
        totalExpansionNeeded = targetSize - originalDimension
        
        # Find all constraining pads and calculate available space in each direction
        positiveConstraints = []  # Pads that constrain positive direction expansion
        negativeConstraints = []  # Pads that constrain negative direction expansion
        
        for i, pad in enumerate(allPads):
            if i == targetIndex:
                continue
                
            # Calculate relative position
            dx = pad['x'] - targetPad['x']
            dy = pad['y'] - targetPad['y']
            
            if dimension == 'width':
                # For width optimization, check horizontal constraints
                # Only consider pads that overlap vertically (could interfere horizontally)
                verticalOverlapThreshold = (pad['height'] + targetPad['height']) / 2 + minGabBetweenPads
                
                if abs(dy) < verticalOverlapThreshold:
                    # This pad could constrain horizontal expansion
                    
                    # Calculate current edge-to-edge gap in X direction
                    currentGapX = abs(dx) - (pad['width'] + targetPad['width']) / 2
                    
                    # Calculate maximum expansion possible before violating minGabBetweenPads
                    maxExpansionTowardThisPad = max(0, currentGapX - minGabBetweenPads)
                    
                    # Determine which direction this pad constrains
                    if dx > 0:
                        # Constraining pad is to the RIGHT (positive X direction)
                        positiveConstraints.append({
                            'padIndex': i,
                            'distance': dx,
                            'maxExpansion': maxExpansionTowardThisPad
                        })
                    else:
                        # Constraining pad is to the LEFT (negative X direction)  
                        negativeConstraints.append({
                            'padIndex': i,
                            'distance': abs(dx),
                            'maxExpansion': maxExpansionTowardThisPad
                        })
                            
            else:  # dimension == 'height'
                # For height optimization, check vertical constraints
                # Only consider pads that overlap horizontally (could interfere vertically)
                horizontalOverlapThreshold = (pad['width'] + targetPad['width']) / 2 + minGabBetweenPads
                
                if abs(dx) < horizontalOverlapThreshold:
                    # This pad could constrain vertical expansion
                    
                    # Calculate current edge-to-edge gap in Y direction
                    currentGapY = abs(dy) - (pad['height'] + targetPad['height']) / 2
                    
                    # Calculate maximum expansion possible before violating minGabBetweenPads
                    maxExpansionTowardThisPad = max(0, currentGapY - minGabBetweenPads)
                    
                    # Determine which direction this pad constrains
                    if dy > 0:
                        # Constraining pad is ABOVE (positive Y direction)
                        positiveConstraints.append({
                            'padIndex': i,
                            'distance': dy,
                            'maxExpansion': maxExpansionTowardThisPad
                        })
                    else:
                        # Constraining pad is BELOW (negative Y direction)
                        negativeConstraints.append({
                            'padIndex': i,
                            'distance': abs(dy),
                            'maxExpansion': maxExpansionTowardThisPad
                        })
        
        # Calculate maximum expansion possible in each direction
        # For each direction, the limiting factor is the most restrictive constraint
        maxPositiveExpansion = min([c['maxExpansion'] for c in positiveConstraints]) if positiveConstraints else totalExpansionNeeded
        maxNegativeExpansion = min([c['maxExpansion'] for c in negativeConstraints]) if negativeConstraints else totalExpansionNeeded
        
        # Determine optimal expansion strategy
        finalDimension = originalDimension
        expansionStrategy = "none"
        
        # Strategy 1: Try symmetrical expansion (expand equally in both directions)
        if maxPositiveExpansion > 0 and maxNegativeExpansion > 0:
            # Both directions have some space
            symmetricalExpansion = min(maxPositiveExpansion, maxNegativeExpansion) * 2  # Total expansion from both sides
            
            if symmetricalExpansion >= totalExpansionNeeded:
                # Symmetrical expansion can achieve target size
                finalDimension = targetSize
                expansionStrategy = "symmetrical"
            else:
                # Partial symmetrical expansion + directional expansion
                remainingExpansion = totalExpansionNeeded - symmetricalExpansion
                
                if maxPositiveExpansion > maxNegativeExpansion:
                    # More space in positive direction
                    additionalExpansion = min(remainingExpansion, maxPositiveExpansion - min(maxPositiveExpansion, maxNegativeExpansion))
                    finalDimension = originalDimension + symmetricalExpansion + additionalExpansion
                    expansionStrategy = "symmetrical + positive"
                else:
                    # More space in negative direction  
                    additionalExpansion = min(remainingExpansion, maxNegativeExpansion - min(maxPositiveExpansion, maxNegativeExpansion))
                    finalDimension = originalDimension + symmetricalExpansion + additionalExpansion
                    expansionStrategy = "symmetrical + negative"
        
        # Strategy 2: Directional expansion only
        elif maxPositiveExpansion > 0:
            # Only positive direction has space
            expansion = min(totalExpansionNeeded, maxPositiveExpansion)
            finalDimension = originalDimension + expansion
            expansionStrategy = "positive only"
            
        elif maxNegativeExpansion > 0:
            # Only negative direction has space
            expansion = min(totalExpansionNeeded, maxNegativeExpansion)
            finalDimension = originalDimension + expansion
            expansionStrategy = "negative only"
        
        # Apply absolute maximum limit (never exceed minPadSize)
        finalDimension = min(finalDimension, minPadSize)
        
        # Debug logging for troubleshooting
        if finalDimension > originalDimension:
            debug_log(f"  {dimension} expansion analysis:")
            debug_log(f"    Original: {originalDimension:.3f}mm -> Final: {finalDimension:.3f}mm")
            debug_log(f"    Target size: {targetSize:.3f}mm, Expansion needed: {totalExpansionNeeded:.3f}mm")
            debug_log(f"    Positive constraints: {len(positiveConstraints)}, max expansion: {maxPositiveExpansion:.3f}mm")
            debug_log(f"    Negative constraints: {len(negativeConstraints)}, max expansion: {maxNegativeExpansion:.3f}mm")
            debug_log(f"    Strategy: {expansionStrategy}")
            if finalDimension >= minPadSize:
                debug_log(f"    NOTE: Achieved target size ({minPadSize}mm)")
        
        return finalDimension


    def projectPadDimension(self, pad_info, direction_x, direction_y):
        """Project pad's half-dimension onto a given direction"""
        import math
        
        angleRad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Pad's local axes in global coordinates
        pad_Xaxis = (math.cos(angleRad), math.sin(angleRad))
        pad_Yaxis = (-math.sin(angleRad), math.cos(angleRad))
        
        # Project pad dimensions onto the given direction
        proj_x = abs(half_w * (pad_Xaxis[0] * direction_x + pad_Xaxis[1] * direction_y))
        proj_y = abs(half_h * (pad_Yaxis[0] * direction_x + pad_Yaxis[1] * direction_y))
        
        return proj_x + proj_y

    def findPadGroups(self, allPads):
        """Group pads that are close to each other and need uniform shrinking"""
        import math
        
        groups = []
        processed = set()
        
        for i, pad in enumerate(allPads):
            if i in processed:
                continue
                
            # Start a new group with this pad
            currentGroup = [i]
            processed.add(i)
            
            # Find all pads connected to this group
            changed = True
            while changed:
                changed = False
                for j, otherPad in enumerate(allPads):
                    if j in processed:
                        continue
                        
                    # Check if this pad is close to any pad in the current group
                    for group_idx in currentGroup:
                        groupPad = allPads[group_idx]
                        dx = otherPad['x'] - groupPad['x']
                        dy = otherPad['y'] - groupPad['y']
                        distance = math.sqrt(dx*dx + dy*dy)
                        
                        # Consider pads close if they're within 2x the minimum mask width
                        maxDimension = max(groupPad['width'], groupPad['height'], 
                                          otherPad['width'], otherPad['height'])
                        threshold = maxDimension + minGabBetweenPads * 2
                        
                        if distance < threshold:
                            currentGroup.append(j)
                            processed.add(j)
                            changed = True
                            break
                    
                    if changed:
                        break
            
            groups.append(currentGroup)
        
        return groups

    def calculateGroupShrinkFactor(self, groupIndices, allPads):
        """Calculate separate shrink factors for width and height for a group of closely packed pads"""
        import math
        
        if len(groupIndices) <= 1:
            return {'width': 1.0, 'height': 1.0}  # No shrinking needed for single pads
        
        groupPads = [allPads[i] for i in groupIndices]
        
        # Find the most constraining pad pairs for each direction
        minWidthShrink = 1.0
        minHeightShrink = 1.0
        
        for i, pad1 in enumerate(groupPads):
            for j, pad2 in enumerate(groupPads):
                if i >= j:
                    continue
                    
                dx = pad2['x'] - pad1['x']
                dy = pad2['y'] - pad1['y']
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < 0.001:
                    continue
                
                # Check X-direction constraint (pads side-by-side)
                if abs(dx) > abs(dy) * 1.5:  # Primarily X-direction separation
                    pad1HalfWidth = pad1['width'] / 2
                    pad2HalfWidth = pad2['width'] / 2
                    currentGap = abs(dx) - pad1HalfWidth - pad2HalfWidth
                    
                    if currentGap < minGabBetweenPads:
                        requiredShrink = (abs(dx) - minGabBetweenPads) / (pad1HalfWidth + pad2HalfWidth)
                        minWidthShrink = min(minWidthShrink, requiredShrink)
                
                # Check Y-direction constraint (pads above/below each other)
                elif abs(dy) > abs(dx) * 1.5:  # Primarily Y-direction separation
                    pad1HalfHeight = pad1['height'] / 2
                    pad2HalfHeight = pad2['height'] / 2
                    currentGap = abs(dy) - pad1HalfHeight - pad2HalfHeight
                    
                    if currentGap < minGabBetweenPads:
                        requiredShrink = (abs(dy) - minGabBetweenPads) / (pad1HalfHeight + pad2HalfHeight)
                        minHeightShrink = min(minHeightShrink, requiredShrink)
                
                # Check diagonal constraints (pads close in both directions)
                else:
                    # Both X and Y constraints may apply
                    pad1HalfWidth = pad1['width'] / 2
                    pad2HalfWidth = pad2['width'] / 2
                    pad1HalfHeight = pad1['height'] / 2
                    pad2HalfHeight = pad2['height'] / 2
                    
                    currentGapX = abs(dx) - pad1HalfWidth - pad2HalfWidth
                    currentGapY = abs(dy) - pad1HalfHeight - pad2HalfHeight
                    
                    if currentGapX < minGabBetweenPads:
                        requiredShrinkX = (abs(dx) - minGabBetweenPads) / (pad1HalfWidth + pad2HalfWidth)
                        minWidthShrink = min(minWidthShrink, requiredShrinkX)
                    
                    if currentGapY < minGabBetweenPads:
                        requiredShrinkY = (abs(dy) - minGabBetweenPads) / (pad1HalfHeight + pad2HalfHeight)
                        minHeightShrink = min(minHeightShrink, requiredShrinkY)
        
        # Ensure minimum pad size (don't shrink below 0.1mm)
        for pad in groupPads:
            if pad['width'] * minWidthShrink < minPadSize:
                minWidthShrink = max(minWidthShrink, minPadSize / pad['width'])
            if pad['height'] * minHeightShrink < minPadSize:
                minHeightShrink = max(minHeightShrink, minPadSize / pad['height'])
        
        return {
            'width': max(minPadSize, minWidthShrink),
            'height': max(minPadSize, minHeightShrink)
        }

        
    def generatePads(self, board):
        """Generate SCAD code for all SMD pads with narrow pad optimization"""
        scad = ""  
        
        # Determine PCB center coordinates
        pcbRect = self.findShapeOnLayer(board, pcbnew.User_4)
        if pcbRect:
            centerX = pcbRect[0] + pcbRect[2]/2
            centerY = pcbRect[1] + pcbRect[3]/2
        else:
            bbox = board.GetBoundingBox()
            centerX = bbox.GetCenter().x
            centerY = bbox.GetCenter().y

        # Collect all SMD pad information
        padsInfo = []
        for module in board.GetFootprints():
            for pad in module.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    padLayers = pad.GetLayerSet()
                    isFrontCopper = padLayers.Contains(pcbnew.F_Cu)
                    isBackCopper = padLayers.Contains(pcbnew.B_Cu)
                    shouldInclude = False
                    
                    # Check if pad should be included based on selected copper side
                    if frontCopperPads and isFrontCopper:
                        shouldInclude = True
                    if backCopperPads and isBackCopper:
                        shouldInclude = True
                        
                    if shouldInclude:
                        pos = pad.GetPosition()
                        size = pad.GetSize()
                        angle = pad.GetOrientation().AsDegrees()
                        x = self.mm(pos.x - centerX)
                        y = self.mm(pos.y - centerY)
                        
                        # Mirror X coordinate for back side
                        if backCopperPads:
                            x = -x
                            
                        padsInfo.append({
                            'x': x,
                            'y': y,
                            'width': self.mm(size.x),
                            'height': self.mm(size.y),
                            'angle': angle,
                            'pad': pad
                        })

        if not padsInfo:
            return "    // No SMD pads found matching layer criteria\n"

        # STEP 1: Optimize narrow pads first (expand them to use available space)
        # This must be done BEFORE group shrinking to prevent conflicts
        groupShrinkFactors = self.optimizeNarrowPads(padsInfo, {})
        
        # STEP 2: Apply group shrinking for closely packed pads
        # Only apply to pads that weren't optimized, or if shrinking is more restrictive
        pad_groups = self.findPadGroups(padsInfo)
        for groupIndices in pad_groups:
            shrinkFactors = self.calculateGroupShrinkFactor(groupIndices, padsInfo)
            for idx in groupIndices:
                # Apply shrinking only if pad hasn't been optimized yet
                if idx not in groupShrinkFactors:
                    groupShrinkFactors[idx] = shrinkFactors
                else:
                    # For optimized pads: only apply group shrinking if it's MORE restrictive
                    # This preserves narrow pad optimization while still respecting minimum gaps
                    existingFactors = groupShrinkFactors[idx]
                    
                    # Only override optimization if group shrinking is more restrictive in BOTH dimensions
                    if (shrinkFactors['width'] < existingFactors['width'] and 
                        shrinkFactors['height'] < existingFactors['height']):
                        # Group shrinking is more restrictive, use it
                        groupShrinkFactors[idx] = shrinkFactors
                    # else: keep the existing optimized factors (they provide better pad visibility)

        # STEP 3: Generate SCAD code for all pads using calculated factors
        for i, pad_info in enumerate(padsInfo):
            # Get shrink/expand factors for this pad (default to no change if not calculated)
            shrinkFactors = groupShrinkFactors.get(i, {'width': 1.0, 'height': 1.0})
            
            # Apply factors to original pad dimensions
            adjusted_width = pad_info['width'] * shrinkFactors['width']
            adjusted_height = pad_info['height'] * shrinkFactors['height']
            
            # Generate SCAD square command for this pad
            scad += f"    translate([{pad_info['x']}, {pad_info['y']}]) "
            scad += f"rotate([0, 0, {pad_info['angle']}]) "
            scad += f"square([{adjusted_width}, {adjusted_height}], center=true);\n"

        return scad
    
    def generateAlignmentHoles(self, board):
        alignmentHoles = self.findCirclesOnLayer(board, pcbnew.User_2)
        if not alignmentHoles:
            return "    // No alignment holes found on User.2 layer\n"

        pcbRect = self.findShapeOnLayer(board, pcbnew.User_4)
        if pcbRect:
            centerX = pcbRect[0] + pcbRect[2]/2
            centerY = pcbRect[1] + pcbRect[3]/2
        else:
            bbox = board.GetBoundingBox()
            centerX = bbox.GetCenter().x
            centerY = bbox.GetCenter().y

        scad = ""
        for hole in alignmentHoles:
            # Bereken lokale coördinaten t.o.v. het midden
            x = self.mm(hole[0] - centerX)
            y = self.mm(hole[1] - centerY)
            radius = self.mm(hole[2])  # Gebruik werkelijke radius
            diameter = radius * 2
            # Spiegel X-coördinaat voor Back (net zoals bij pads)
            if backCopperPads:
                x = -x
            scad += f"    translate([{x}, {y}, -0.005]) cylinder(h=frameHeight + 0.01, d={diameter}, center=false);\n"
        return scad

    def findShapeOnLayer(self, board, layer):
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_RECT and
                    drawing.GetLayer() == layer):
                return (drawing.GetStart().x, drawing.GetStart().y,
                        drawing.GetEnd().x - drawing.GetStart().x,
                        drawing.GetEnd().y - drawing.GetStart().y)
        return None

    def findCirclesOnLayer(self, board, layer):
        circles = []
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_CIRCLE and
                    drawing.GetLayer() == layer):
                center = drawing.GetCenter()
                circles.append((center.x, center.y, drawing.GetRadius()))
        return circles

    def mm(self, nm):
        return nm / 1e6


    def debugAllLayers(self, board):
        """Debug function to list all layers with drawings"""
        try:
            debug_log = self.get_debug_log_function()
            
            debug_log("=== ALL LAYERS ANALYSIS ===")
            
            layer_counts = {}
            for drawing in board.GetDrawings():
                layer = drawing.GetLayer()
                if layer not in layer_counts:
                    layer_counts[layer] = 0
                layer_counts[layer] += 1
            
            debug_log(f"Total drawings: {sum(layer_counts.values())}")
            for layer, count in sorted(layer_counts.items()):
                debug_log(f"Layer {layer}: {count} drawings")
                
            debug_log(f"Edge_Cuts constant value: {pcbnew.Edge_Cuts}")
            debug_log("")  # Empty line for readability
            
        except Exception as e:
            print(f"Debug error: {e}")


StencilGenerator().register()
