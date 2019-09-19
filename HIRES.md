# Hires

## Releases
Hires packages can be automatically generated using the [hires](hires.py) script, but several prebuilt packages are provided on the [releases](https://github.com/kcghost/wadsnip/releases) page.
Using the script offers more flexibility, but it requires a lot of CPU time or an NVIDIA GPU, and the releases contain extra fixes and optimizations.

## Requirements
* Use GZDoom >= 4.1.0
* Do not use brightmaps, they are not compatible at this time

## Gameplay Recommendations
* `Options>Display options>Texture options>Texture Filter mode>Precache GL textures>Yes`. This will cause a delay in load time at level start, but avoids some stuttering during gameplay.
* Not actually needed when using hires, but just generally: `Options>Display options>Texture options>Texture Filter mode>None`
It's also fun to play around with the pixel scalars in that menu, but hires packs do a better job.
* The default option for [sprite clipping](https://zdoom.org/wiki/OpenGL_options) in GZDoom is 'smart', which appears to fix examples like the marine bodies in E1M1 when played with just the IWAD, but curiously not when playing with a PWAD that replaces them (even with the exact same lump). You may wish to adjust `Options>Display Options>Hardware Renderer>Adjust sprite clipping` to 'Always' or 'Smarter'.

## Known Issues
* Replacing textures in a PWAD changes the behavior of 'sprite clipping'
* SmoothDoom has an issue with the status bar graphics that is manually fixed in release by moving them to the proper namespace.
* PNG files are optimized in the releases with 'pngquant', which results in a faster load time than those simply generated from the script.
* GZDoom defines a decal that uses a normal sprite image, but the decal definition does not take into account that the sprite is scaled. The decal is redefined with the proper scaling in release.

## Notes
High resolution packages for DOOM have quite a few technical gotchas:
* The upscaling process uses the games palette to create regular truecolor PNG images. Therefore compatibility with palette changing mods is broken, and some in game performance is lost.
* These packages are made against specific combinations of IWADs and PWADs, so compatability with other graphical mods is not always a given.
* STEP1 and STEP2 are names for both flats and walltextures. GZDoom offers a 'hires' folder for replacing all graphics, but places them all in the same namespace, so conflicts like this are problematic. Wadsnip resolves this by placing all graphics in the patches namespace instead within namespaced folders. It then redefines all graphics in the [TEXTURES.txt](https://zdoom.org/wiki/TEXTURES) lump and specifies full paths to the patches.
* VILE\* is a valid name within a WAD file, but not a PK3 due to the backslash. GZDoom allows for the use of ^(caret) to represent the backslash, but only in sprites/ and voxels/ namespaces. Wadsnip uses the caret for the patch name in TEXTURES.
* Neural net upscalers such as waifu2x do not currently handle the alpha layer well, or at all really. This is a big problem for sprites. Wadsnip instead scales with XBRZ pixel art scaler alongside waifu2x to generate an alpha mask to use.
* In order for the XBRZ scaler to work best, the canvas must be larger than the original image in many cases. Sometimes this results in a slightly larger sprite. Wadsnip currently crops it back down to original size, but it might be best to retain the larger sprite in the future and adjust offsets accordingly.
* Since hires packages replace graphics within a PWAD, [brightmaps](https://zdoom.org/wiki/GLDEFS#Brightmaps) from GZDoom are not compatible. They often specify they should only take affect for lumps not replaced by a PWAD, and they probably need to be scaled anyway.
* DOOM wall textures are 'composite' images composed from 'patch' images. It is possible to scale either the patches themselves, or just the resulting textures. Wadsnip scales the resulting textures; it is easier to manage that way. Scaling patches requires redefining the textures anyway to specify the scaling, and composing the texture beforehand results in less transparency. The more images without transparency, the better as it results in less calls to XBRZ creating potentially awkward edges. If there was a way in GZDOOM to hires a patch without redefining the associated textures, then there would be a downside to this approach in that custom textures from unknown PWADs that use the original patches could not take advantage of the scaling.
* Final DOOM (Evilution and Plutonia) does some really odd tricks with textures. In some instances they essentially make what *should* have been a wall texture by separating a wall into several small sections that are too small to display the whole texture, so you get a repeating pattern of just part of the texture. It doesn't look as good with hires, you might notice seams. (And again, *should* have just been a new composite texture definition, you can do that easily, and it would have scaled better). Other times the textures themselves are huge and repeat with several different wall sections, and only one portion is used by some mechanism. Again, doesn't make sense to me, but at least it renders fine in game.
* Sprites have a special mechanism by which they can two rotations by mirroring. If a PWAD is used which defines the extra rotations, the mirror sprite must be ignored.

## TODO
* Could fix sprite clipping with hacks=True?
* PIL Can't read all PNG images
* Out of memory errors when multiprocessing with CUDA/Cupy.
* hires gzdoom resources.
* hires decals.
* hires brightmaps.
* hires dynamically larger canvas
* Support DOOM 64?
* Support Adventures of Square (parse textures text format)?
* Support the wadsmoosh IWAD for hires.
