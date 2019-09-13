freedoom_wads := iwads/freedoom1.wad iwads/freedoom2.wad iwads/freedm.wad
doom1_wads := iwads/doom.wad iwads/doomu.wad iwads/doombfg.wad
doom2_wads := iwads/doom2.wad iwads/doom2bfg.wad iwads/tnt.wad iwads/plutonia.wad
scales := 2 4 8

all: $(foreach hires_n,doom_sprfix doom_smoothdoom freedoom,out/$(hires_n)_hires.zip $(foreach scale,$(scales),out/$(hires_n)_hires_$(scale)x.pk3)) out/freedoom_bleeps.pk3 out/doom_bleeps.pk3

.PHONY: clean veryclean all

SHELL := /bin/bash
.SHELLFLAGS := -ec
.ONESHELL:

# GZDoom has a builtin decaldef.txt that uses the plasma gun sprites PLSSA0 and PLSSB0, and apparently doesn't take into account the scaling in the texture
define decaldef_fix =
decal PlasmaScorch1
{
	pic PLSSA0
	x-scale $(1)
	y-scale $(1)
	add 1.0
	fullbright
	animator GoAway
	lowerdecal PlasmaScorchLower1
}

decal PlasmaScorch2
{
	pic PLSSB0
	x-scale $(1)
	y-scale $(1)
	add 1.0
	fullbright
	animator GoAway
	lowerdecal PlasmaScorchLower2
}
endef

# SmoothDoom places status bar graphics in 'sprites', and for some reason that messes up scaling when used in hires for a frame or two. Still don't know exactly why.
# So fix it up and used a modified version when generating the hires package
out/SmoothDoom_fixed.pk3: pwads/SmoothDoom.pk3
	yes | unzip $< -d out/SmoothDoom
	mkdir -p out/SmoothDoom/GRAPHICS
	mv out/SmoothDoom/SPRITES/MUGSHOT out/SmoothDoom/GRAPHICS/
	cd out/SmoothDoom/
	zip -r ../$(notdir $@) *

out/SmoothDoom/Credits.txt: pwads/SmoothDoom.pk3
	yes | unzip $< -d out/SmoothDoom
	touch $@

define post_hires =
	cd $(basename $@)
	echo "$(call decaldef_fix,$(shell echo 'scale=3;1/$*' | bc))" > decaldef.hires
	find . -name "*.png" -print0 | xargs -0 -n 50 -P 12 pngquant --ext .png --force
	# Used 'stored' for better in-game performance, faster load times
	# From my testing, GZDoom seems to prefer individual PNGs as small/compressed as possible, but ZIP compression on the whole archive increases load time
	zip -0 -r ../$(notdir $@) *
endef

out/doom_sprfix_hires_%x.pk3: $(foreach iwad,$(doom1_wads) $(doom2_wads),$(iwad)) pwads/sprfix19/D1SPFX19.WAD pwads/sprfix19/D2SPFX19.WAD pwads/sprfix19/D1DEHFIX.DEH pwads/sprfix19/D2DEHFIX.DEH
	rm -rf $(basename $@)
	python3 hires.py -nopk3 -path $(basename $@) $(foreach iwad,$(doom1_wads),-iwad $(iwad) pwads/sprfix19/D1SPFX19.WAD) $(foreach iwad,$(doom2_wads),-iwad $(iwad) pwads/sprfix19/D2SPFX19.WAD) -gpu 0 -scale $*
	cp pwads/sprfix19/D1DEHFIX.DEH $(basename $@)/filter/doom.id.doom1/dehacked.sprfix
	cp pwads/sprfix19/D2DEHFIX.DEH $(basename $@)/filter/doom.id.doom2/dehacked.sprfix
	$(post_hires)

out/doom_smoothdoom_hires_%x.pk3: $(foreach iwad,$(doom1_wads) $(doom2_wads),$(iwad)) out/SmoothDoom_fixed.pk3
	rm -rf $(basename $@)
	python3 hires.py -nopk3 -path $(basename $@) $(foreach iwad,$(doom1_wads) $(doom2_wads),-iwad $(iwad) out/SmoothDoom_fixed.pk3) -gpu 0 -scale $* 
	$(post_hires)

out/freedoom_hires_%x.pk3: $(foreach iwad,$(freedoom_wads),$(iwad))
	rm -rf $(basename $@)
	python3 hires.py -nopk3 -path $(basename $@) $(foreach iwad,$(freedoom_wads),-iwad $(iwad)) -gpu 0 -scale $*
	$(post_hires)

out/%_bleeps.pk3:
	rm -rf $(basename $@)
	python3 bleeps.py -nopk3 -path $(basename $@) $(foreach iwad,$^,-iwad $(iwad))
	cd $(basename $@)
	zip -0 -r ../$(notdir $@) *

out/freedoom_bleeps.pk3: $(foreach iwad,$(freedoom_wads),$(iwad))
out/doom_bleeps.pk3: $(foreach iwad,$(doom1_wads) $(doom2_wads),$(iwad))

out/doom_sprfix_hires.zip: $(foreach scale,$(scales),out/doom_sprfix_hires_$(scale)x.pk3) res/doom_hires_sprfix.txt pwads/sprfix19/SPRFIX19.txt
out/doom_smoothdoom_hires.zip: $(foreach scale,$(scales),out/doom_smoothdoom_hires_$(scale)x.pk3) res/doom_hires_smoothdoom.txt out/SmoothDoom/Credits.txt
out/freedoom_hires.zip: $(foreach scale,$(scales),out/freedoom_hires_$(scale)x.pk3) res/freedoom_hires.txt res/freedoom_copying.txt res/freedoom_credits.txt

out/%.zip:
	zip -9 -j $@ $^

clean:
	rm -rf out/*

veryclean: clean
	rm -rf _cache

# https://www.cmcrossroads.com/article/printing-value-makefile-variable
print-%  : ; @echo $* = $($*)
