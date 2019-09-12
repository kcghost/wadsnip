# Wadsnip

A bunch of python scripts that do cool stuff with Doom wads and PK3 archives.

### hires
Generate your own high resolution PK3s with the help of Neural Net upscaling!
Uses waifu2x with xbrz to determine the alpha layer. Generates a filtered PK3 capable of supporting all specified IWAD chains. See [HIRES](HIRES.md) for details and pre-built releases.

```
python3 hires.py -iwad iwads/doom.wad -iwad iwads/doomu.wad -iwad iwads/doom2.wad -iwad iwads/tnt.wad -iwad iwads/plutonia.wad -gpu 0 -scale 4
python3 hires.py -iwad iwads/freedoom1.wad -iwad iwads/freedoom2.wad -iwad iwads/freedm.wad -gpu 0 -scale 4
```

### extract
Extract any wad or PK3 into namespaced folders and a PK3. Also supports a `--modernize` option that converts as many formats as possible into modern readable equivalents. See `./extract.py -h` for details.
```
python3 extract.py -iwad iwads/doomu.wad --modernize
```

## Setup
*Only tested on Linux, sorry. Might work on Windows with Python/MinGW.*
```
git clone https://github.com/kcghost/wadsnip.git
git submodule update --init --recursive
cd xbrzscale
sudo apt install libsdl2-dev libsdl2-image-dev
make
cd ..
pip3 install soundfile
pip3 install pillow
pip3 install chainer
pip3 install cupy101
```
[xbrzscale](https://github.com/atheros/xbrzscale) and [waifu2x-chainer](https://github.com/tsurumeso/waifu2x-chainer) only needed for hires functionality.
Cupy is only needed if you want to speed up generation of hires packages with the use of a GPU. See [waifu2x-chainer](https://github.com/tsurumeso/waifu2x-chainer) for details.

## TODO
* PC speaker pack generator
* PWAD filter merge (Music packs as example)
* IWAD smoosh
* Map pack smoosh
* Define keywords and expected structure for info parsing (regex findall tuples?)
* mkpk3 utility
* Dummy IWAD generator
* Determine wad graphics by whatever is an image type that is not in pnames
* Use photogrammetry to generate more sprite rotations.

## Licensing
Wadsnip is licensed under GPL v3.

## Contributions
There is a core set of functionality under [doom](doom/) that is at least somewhat extensible, and plenty of interesting things you can do with the code that are not fully demonstrated.
Please feel free to fork this project to add new functionality and scripts. Make a pull request if you think your code is universally useful and follows the following vague rules:
1. The project structure is such that user interactable scripts should be short and sweet, mostly just argument parsing for a function in [doom.util](doom/util.py).
2. All functions in [doom.util](doom/util.py) should provide their own imports to avoid unnecessary dependencies. (A user shouldn't be forced to install PIL or chainer for a simple lump extraction for example).
3. I actively despise PEP8, so don't worry about that. Honestly just make sure you use tabs. *Tabs* in **Python**? I know, I'm a terrible person.
4. TBD.
