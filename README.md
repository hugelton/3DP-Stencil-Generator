# 3DP-Stencil-Generator
KiCad 3D Printable Stencil Generator Plugin

## Features

- Generates a stencil frame based on the Edge.Cuts (PCB outline) or User.3 layer
- Creates pad cutouts based on SMD pads
- Adds alignment pin holes based on circles on User.2 layer
- Outputs an OpenSCAD file for easy customization and 3D printing
- Automatically opens the output folder after generation for quick access

## Installation

1. Clone or download this repository.
2. Copy the "3dp-stencil-generator" folder to your KiCad plugins directory:
   - Windows: `C:\Program Files\KiCad\share\kicad\scripting\plugins`
   - Linux: `/usr/share/kicad/scripting/plugins`
   - macOS: `/Applications/KiCad/KiCad.app/Contents/SharedSupport/scripting/plugins`

## Settings

In the `__init__.py` program you can tweak some settings to your needs.
<pre>
# === Global configuration ===
BUILD = "121"            # Build number
workDir = "stencil"      # Working folder name
front_copper_pads = True # Generate front copper pads
back_copper_pads = False # Generate back copper pads
min_mask_width = 0.40    # Minimum mask width (mm) between pads
min_pad_size = 0.40      # Minimum pad size (mm) after shrinking
pcbClearance = 0.15      # PCB clearance (mm) - moves outline outward from Edge.Cuts
</pre>

## Usage

1. In KiCad PCB Editor:
  - 1.1 Draw a rectangle on User.3 layer to define the stencil frame.
  - 1.2. If no User.3 layer is present, or if it doesn’t contain a rectangle, the stencil frame is derived from the Edge.Cuts layer (+5mm in all directions).
2. In KiCad PCB Editor:
  - 2.1. Draw a rectangle on User.4 layer to define the PCB outline.
  - 2.2. If no User.4 layer is present, or if it doesn’t contain a rectangle, the PCB outline is derived from the Edge.Cuts layer.
3. (Optional) Draw circles on User.2 layer to define alignment pin positions.
4. Click the ![icon](https://github.com/hugelton/3DP-Stencil-Generator/blob/99ac4820377e08e7fa33e80fa1f7343ff17766b6/3dp-stencil-generator/icon.png)"3D Printable Stencil Generator" button in the toolbar.
   - A parameter dialog will appear where you can configure settings interactively
   - Alternatively, you can modify the default values in the `__init__.py` file
5. The plugin will create a working directory ("/stencil" defined in the `__init__.py` program) in the same directory as your PCB file and then generate an OpenSCAD file in that directory.
   - The stencil folder will automatically open in your file explorer after generation
6. Open the generated OpenSCAD file to customize parameters if needed.
7. Render and export the stencil as an STL file for 3D printing.

## Contributors

- [mrWheel](https://github.com/mrWheel) - Added Edge.Cuts support, GUI dialog, and advanced pad spacing algorithms
- **Leo Kuroshita** ([Hugelton Instruments](https://github.com/hugelton)) - Original author and maintainer

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
