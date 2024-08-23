# 3DP-Stencil-Generator
KiCad 3D Printable Stencil Generator Plugin

## Features

- Generates a stencil frame based on User.8 layer
- Creates pad cutouts based on SMD pads
- Adds alignment pin holes based on circles on User.7 layer
- Outputs an OpenSCAD file for easy customization and 3D printing

## Installation

1. Clone or download this repository.
2. Copy the "3dp-stencil-generator" folder to your KiCad plugins directory:
   - Windows: `C:\Program Files\KiCad\share\kicad\scripting\plugins`
   - Linux: `/usr/share/kicad/scripting/plugins`
   - macOS: `/Applications/KiCad/KiCad.app/Contents/SharedSupport/scripting/plugins`

## Usage

1. In KiCad PCB Editor, draw a rectangle on User.8 layer to define the stencil frame.
2. Draw a rectangle on User.9 layer to define the PCB outline.
3. (Optional) Draw circles on User.7 layer to define alignment pin positions.
4. Click the ![icon](https://github.com/hugelton/3DP-Stencil-Generator/blob/99ac4820377e08e7fa33e80fa1f7343ff17766b6/3dp-stencil-generator/icon.png)"3D Printable Stencil Generator" button in the toolbar.
5. The plugin will generate an OpenSCAD file in the same directory as your PCB file.
6. Open the generated OpenSCAD file to customize parameters if needed.
7. Render and export the stencil as an STL file for 3D printing.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
