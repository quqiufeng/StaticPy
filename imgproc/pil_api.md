# Pillow 公开 API 清单（自省生成）

> 由 `imgproc/pil_surface.py` 自动生成。每个名字对应一个待迁移的接口。

## Image  （函数 39，类 19）

| 函数 | 签名 |
|---|---|
| `alpha_composite` | `(im1: 'Image', im2: 'Image') -> 'Image'` |
| `blend` | `(im1: 'Image', im2: 'Image', alpha: 'float') -> 'Image'` |
| `cast` | `(typ, val)` |
| `composite` | `(image1: 'Image', image2: 'Image', mask: 'Image') -> 'Image'` |
| `deprecate` | `(deprecated: 'str', when: 'int | None', replacement: 'str | None' = None, *, action: 'str | None' = None, plural: 'bool' = False, stacklevel: 'int' = 3) -> 'None'` |
| `effect_mandelbrot` | `(size: 'tuple[int, int]', extent: 'tuple[float, float, float, float]', quality: 'int') -> 'Image'` |
| `effect_noise` | `(size: 'tuple[int, int]', sigma: 'float') -> 'Image'` |
| `eval` | `(image: 'Image', *args: 'Callable[[int], float]') -> 'Image'` |
| `fromarray` | `(obj: 'SupportsArrayInterface', mode: 'str | None' = None) -> 'Image'` |
| `fromarrow` | `(obj: 'SupportsArrowArrayInterface', mode: 'str', size: 'tuple[int, int]') -> 'Image'` |
| `frombuffer` | `(mode: 'str', size: 'tuple[int, int]', data: 'bytes | SupportsArrayInterface', decoder_name: 'str' = 'raw', *args: 'Any') -> 'Image'` |
| `frombytes` | `(mode: 'str', size: 'tuple[int, int]', data: 'bytes | bytearray | SupportsArrayInterface', decoder_name: 'str' = 'raw', *args: 'Any') -> 'Image'` |
| `fromqimage` | `(im: 'ImageQt.QImage') -> 'ImageFile.ImageFile'` |
| `fromqpixmap` | `(im: 'ImageQt.QPixmap') -> 'ImageFile.ImageFile'` |
| `getmodebandnames` | `(mode: 'str') -> 'tuple[str, ...]'` |
| `getmodebands` | `(mode: 'str') -> 'int'` |
| `getmodebase` | `(mode: 'str') -> 'str'` |
| `getmodetype` | `(mode: 'str') -> 'str'` |
| `i32le` | `(c: 'bytes', o: 'int' = 0) -> 'int'` |
| `init` | `() -> 'bool'` |
| `isImageType` | `(t: 'Any') -> 'TypeGuard[Image]'` |
| `is_path` | `(f: 'Any') -> 'TypeGuard[StrOrBytesPath]'` |
| `linear_gradient` | `(mode: 'str') -> 'Image'` |
| `merge` | `(mode: 'str', bands: 'Sequence[Image]') -> 'Image'` |
| `new` | `(mode: 'str', size: 'tuple[int, int] | list[int]', color: 'float | tuple[float, ...] | str | None' = 0) -> 'Image'` |
| `o32be` | `(i: 'int') -> 'bytes'` |
| `o32le` | `(i: 'int') -> 'bytes'` |
| `open` | `(fp: 'StrOrBytesPath | IO[bytes]', mode: "Literal['r']" = 'r', formats: 'list[str] | tuple[str, ...] | None' = None) -> 'ImageFile.ImageFile'` |
| `preinit` | `() -> 'None'` |
| `radial_gradient` | `(mode: 'str') -> 'Image'` |
| `register_decoder` | `(name: 'str', decoder: 'type[ImageFile.PyDecoder]') -> 'None'` |
| `register_encoder` | `(name: 'str', encoder: 'type[ImageFile.PyEncoder]') -> 'None'` |
| `register_extension` | `(id: 'str', extension: 'str') -> 'None'` |
| `register_extensions` | `(id: 'str', extensions: 'list[str]') -> 'None'` |
| `register_mime` | `(id: 'str', mimetype: 'str') -> 'None'` |
| `register_open` | `(id: 'str', factory: 'Callable[[IO[bytes], str | bytes], ImageFile.ImageFile] | type[ImageFile.ImageFile]', accept: 'Callable[[bytes], bool | str] | None' = None) -> 'None'` |
| `register_save` | `(id: 'str', driver: 'Callable[[Image, IO[bytes], str | bytes], None]') -> 'None'` |
| `register_save_all` | `(id: 'str', driver: 'Callable[[Image, IO[bytes], str | bytes], None]') -> 'None'` |
| `registered_extensions` | `() -> 'dict[str, str]'` |

- **DecompressionBombError** (3 成员): add_note, args, with_traceback
- **DecompressionBombWarning** (3 成员): add_note, args, with_traceback
- **DeferredError** (1 成员): new
- **Dither** (15 成员): FLOYDSTEINBERG, NONE, ORDERED, RASTERIZE, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **Exif** (16 成员): bigtiff, clear, endian, get, get_ifd, hide_offsets, items, keys, load, load_from_fp, pop, popitem, setdefault, tobytes, update, values
- **Image** (59 成员): alpha_composite, apply_transparency, close, convert, copy, crop, draft, effect_spread, entropy, filter, format, format_description, frombytes, get_child_images, getbands, getbbox, getchannel, getcolors, getdata, getexif
- **ImagePointHandler** (1 成员): point
- **ImagePointTransform** (0 成员): 
- **ImageTransformHandler** (1 成员): transform
- **Palette** (13 成员): ADAPTIVE, WEB, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **Quantize** (15 成员): FASTOCTREE, LIBIMAGEQUANT, MAXCOVERAGE, MEDIANCUT, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **Resampling** (17 成员): BICUBIC, BILINEAR, BOX, HAMMING, LANCZOS, NEAREST, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **SupportsArrayInterface** (0 成员): 
- **SupportsArrowArrayInterface** (0 成员): 
- **SupportsGetData** (1 成员): getdata
- **Transform** (16 成员): AFFINE, EXTENT, MESH, PERSPECTIVE, QUAD, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **Transpose** (18 成员): FLIP_LEFT_RIGHT, FLIP_TOP_BOTTOM, ROTATE_180, ROTATE_270, ROTATE_90, TRANSPOSE, TRANSVERSE, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **UnidentifiedImageError** (8 成员): add_note, args, characters_written, errno, filename, filename2, strerror, with_traceback
- **enum** (15 成员): FASTOCTREE, LIBIMAGEQUANT, MAXCOVERAGE, MEDIANCUT, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes

## ImageOps  （函数 20，类 1）

| 函数 | 签名 |
|---|---|
| `autocontrast` | `(image: 'Image.Image', cutoff: 'float | tuple[float, float]' = 0, ignore: 'int | Sequence[int] | None' = None, mask: 'Image.Image | None' = None, preserve_tone: 'bool' = False) -> 'Image.Image'` |
| `cast` | `(typ, val)` |
| `colorize` | `(image: 'Image.Image', black: 'str | tuple[int, ...]', white: 'str | tuple[int, ...]', mid: 'str | int | tuple[int, ...] | None' = None, blackpoint: 'int' = 0, whitepoint: 'int' = 255, midpoint: 'int' = 127) -> 'Image.Image'` |
| `contain` | `(image: 'Image.Image', size: 'tuple[int, int]', method: 'int' = <Resampling.BICUBIC: 3>) -> 'Image.Image'` |
| `cover` | `(image: 'Image.Image', size: 'tuple[int, int]', method: 'int' = <Resampling.BICUBIC: 3>) -> 'Image.Image'` |
| `crop` | `(image: 'Image.Image', border: 'int' = 0) -> 'Image.Image'` |
| `deform` | `(image: 'Image.Image', deformer: 'SupportsGetMesh', resample: 'int' = <Resampling.BILINEAR: 2>) -> 'Image.Image'` |
| `equalize` | `(image: 'Image.Image', mask: 'Image.Image | None' = None) -> 'Image.Image'` |
| `exif_transpose` | `(image: 'Image.Image', *, in_place: 'bool' = False) -> 'Image.Image | None'` |
| `expand` | `(image: 'Image.Image', border: 'int | tuple[int, ...]' = 0, fill: 'str | int | tuple[int, ...]' = 0) -> 'Image.Image'` |
| `fit` | `(image: 'Image.Image', size: 'tuple[int, int]', method: 'int' = <Resampling.BICUBIC: 3>, bleed: 'float' = 0.0, centering: 'tuple[float, float]' = (0.5, 0.5)) -> 'Image.Image'` |
| `flip` | `(image: 'Image.Image') -> 'Image.Image'` |
| `grayscale` | `(image: 'Image.Image') -> 'Image.Image'` |
| `invert` | `(image: 'Image.Image') -> 'Image.Image'` |
| `mirror` | `(image: 'Image.Image') -> 'Image.Image'` |
| `overload` | `(func)` |
| `pad` | `(image: 'Image.Image', size: 'tuple[int, int]', method: 'int' = <Resampling.BICUBIC: 3>, color: 'str | int | tuple[int, ...] | None' = None, centering: 'tuple[float, float]' = (0.5, 0.5)) -> 'Image.Image'` |
| `posterize` | `(image: 'Image.Image', bits: 'int') -> 'Image.Image'` |
| `scale` | `(image: 'Image.Image', factor: 'float', resample: 'int' = <Resampling.BICUBIC: 3>) -> 'Image.Image'` |
| `solarize` | `(image: 'Image.Image', threshold: 'int' = 128) -> 'Image.Image'` |

- **SupportsGetMesh** (1 成员): getmesh

## ImageChops  （函数 21，类 0）

| 函数 | 签名 |
|---|---|
| `add` | `(image1: 'Image.Image', image2: 'Image.Image', scale: 'float' = 1.0, offset: 'float' = 0) -> 'Image.Image'` |
| `add_modulo` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `blend` | `(image1: 'Image.Image', image2: 'Image.Image', alpha: 'float') -> 'Image.Image'` |
| `composite` | `(image1: 'Image.Image', image2: 'Image.Image', mask: 'Image.Image') -> 'Image.Image'` |
| `constant` | `(image: 'Image.Image', value: 'int') -> 'Image.Image'` |
| `darker` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `difference` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `duplicate` | `(image: 'Image.Image') -> 'Image.Image'` |
| `hard_light` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `invert` | `(image: 'Image.Image') -> 'Image.Image'` |
| `lighter` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `logical_and` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `logical_or` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `logical_xor` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `multiply` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `offset` | `(image: 'Image.Image', xoffset: 'int', yoffset: 'int | None' = None) -> 'Image.Image'` |
| `overlay` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `screen` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `soft_light` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |
| `subtract` | `(image1: 'Image.Image', image2: 'Image.Image', scale: 'float' = 1.0, offset: 'float' = 0) -> 'Image.Image'` |
| `subtract_modulo` | `(image1: 'Image.Image', image2: 'Image.Image') -> 'Image.Image'` |


## ImageEnhance  （函数 0，类 4）

- **Brightness** (1 成员): enhance
- **Color** (1 成员): enhance
- **Contrast** (1 成员): enhance
- **Sharpness** (1 成员): enhance

## ImageFilter  （函数 1，类 23）

| 函数 | 签名 |
|---|---|
| `cast` | `(typ, val)` |

- **BLUR** (3 成员): filter, filterargs, name
- **BoxBlur** (2 成员): filter, name
- **BuiltinFilter** (1 成员): filter
- **CONTOUR** (3 成员): filter, filterargs, name
- **Color3DLUT** (4 成员): filter, generate, name, transform
- **DETAIL** (3 成员): filter, filterargs, name
- **EDGE_ENHANCE** (3 成员): filter, filterargs, name
- **EDGE_ENHANCE_MORE** (3 成员): filter, filterargs, name
- **EMBOSS** (3 成员): filter, filterargs, name
- **FIND_EDGES** (3 成员): filter, filterargs, name
- **Filter** (1 成员): filter
- **GaussianBlur** (2 成员): filter, name
- **Kernel** (2 成员): filter, name
- **MaxFilter** (2 成员): filter, name
- **MedianFilter** (2 成员): filter, name
- **MinFilter** (2 成员): filter, name
- **ModeFilter** (2 成员): filter, name
- **MultibandFilter** (1 成员): filter
- **RankFilter** (2 成员): filter, name
- **SHARPEN** (3 成员): filter, filterargs, name
- **SMOOTH** (3 成员): filter, filterargs, name
- **SMOOTH_MORE** (3 成员): filter, filterargs, name
- **UnsharpMask** (2 成员): filter, name

## ImageStat  （函数 0，类 2）

- **Global** (9 成员): count, extrema, mean, median, rms, stddev, sum, sum2, var
- **Stat** (9 成员): count, extrema, mean, median, rms, stddev, sum, sum2, var

## ImageDraw  （函数 6，类 1）

| 函数 | 签名 |
|---|---|
| `Draw` | `(im: 'Image.Image', mode: 'str | None' = None) -> 'ImageDraw'` |
| `Outline` | `(...)` |
| `cast` | `(typ, val)` |
| `deprecate` | `(deprecated: 'str', when: 'int | None', replacement: 'str | None' = None, *, action: 'str | None' = None, plural: 'bool' = False, stacklevel: 'int' = 3) -> 'None'` |
| `floodfill` | `(image: 'Image.Image', xy: 'tuple[int, int]', value: 'float | tuple[int, ...]', border: 'float | tuple[int, ...] | None' = None, thresh: 'float' = 0) -> 'None'` |
| `getdraw` | `(im: 'Image.Image | None' = None, hints: 'list[str] | None' = None) -> 'tuple[ImageDraw2.Draw | None, ModuleType]'` |

- **ImageDraw** (20 成员): arc, bitmap, chord, circle, ellipse, font, getfont, line, multiline_text, multiline_textbbox, pieslice, point, polygon, rectangle, regular_polygon, rounded_rectangle, shape, text, textbbox, textlength

## ImageFont  （函数 8，类 6）

| 函数 | 签名 |
|---|---|
| `TypedDict` | `(typename, fields=None, /, *, total=True, **kwargs)` |
| `cast` | `(typ, val)` |
| `is_path` | `(f: 'Any') -> 'TypeGuard[StrOrBytesPath]'` |
| `load` | `(filename: 'str') -> 'ImageFont'` |
| `load_default` | `(size: 'float | None' = None) -> 'FreeTypeFont | ImageFont'` |
| `load_default_imagefont` | `() -> 'ImageFont'` |
| `load_path` | `(filename: 'str | bytes') -> 'ImageFont'` |
| `truetype` | `(font: 'StrOrBytesPath | BinaryIO', size: 'float' = 10, index: 'int' = 0, encoding: 'str' = '', layout_engine: 'Layout | None' = None) -> 'FreeTypeFont'` |

- **Axis** (11 成员): clear, copy, fromkeys, get, items, keys, pop, popitem, setdefault, update, values
- **DeferredError** (1 成员): new
- **FreeTypeFont** (11 成员): font_variant, get_variation_axes, get_variation_names, getbbox, getlength, getmask, getmask2, getmetrics, getname, set_variation_by_axes, set_variation_by_name
- **ImageFont** (3 成员): getbbox, getlength, getmask
- **Layout** (13 成员): BASIC, RAQM, as_integer_ratio, bit_count, bit_length, conjugate, denominator, from_bytes, imag, is_integer, numerator, real, to_bytes
- **TransposedFont** (3 成员): getbbox, getlength, getmask

## ImageSequence  （函数 1，类 1）

| 函数 | 签名 |
|---|---|
| `all_frames` | `(im: 'Image.Image | list[Image.Image]', func: 'Callable[[Image.Image], Image.Image] | None' = None) -> 'list[Image.Image]'` |

- **Iterator** (0 成员): 

## ImageColor  （函数 1，类 0）

| 函数 | 签名 |
|---|---|
| `lru_cache` | `(maxsize=128, typed=False)` |


## ImagePalette  （函数 8，类 1）

| 函数 | 签名 |
|---|---|
| `load` | `(filename: 'str') -> 'tuple[bytes, str]'` |
| `make_gamma_lut` | `(exp: 'float') -> 'list[int]'` |
| `make_linear_lut` | `(black: 'int', white: 'float') -> 'list[int]'` |
| `negative` | `(mode: 'str' = 'RGB') -> 'ImagePalette'` |
| `random` | `(mode: 'str' = 'RGB') -> 'ImagePalette'` |
| `raw` | `(rawmode: 'str', data: 'Sequence[int] | bytes | bytearray') -> 'ImagePalette'` |
| `sepia` | `(white: 'str' = '#fff0c0') -> 'ImagePalette'` |
| `wedge` | `(mode: 'str' = 'RGB') -> 'ImagePalette'` |

- **ImagePalette** (8 成员): colors, copy, getcolor, getdata, palette, save, tobytes, tostring

