import tensorflow as tf
import tfcv, re
from .convnext import convert_name as convert_name_convnext
from ..openmmlab.util import convert_name_upernet
from ... import upernet, decode, stochasticdepth, convnext
from ... import config as config_
from ...util import *
from .convnext import preprocess, config
from functools import partial

def convert_name(name, basename=None):
    if not basename is None:
        assert name.startswith(basename)
        name = name[len(basename) + 1:]
    if "block" in name or "downsample" in name or "stem" in name:
        name = "backbone." + convert_name_convnext(name)
    elif name.startswith("neck"):
        name = re.sub("^neck/norm/([0-9]*)", lambda m: f"backbone.norm{int(m.group(1)) - 1}", name)
    else:
        name = convert_name_upernet(name)
    return name

decoder_config = config_.PytorchConfig(
    norm=lambda x, *args, **kwargs: tf.keras.layers.BatchNormalization(*args, momentum=0.9, epsilon=1e-5, **kwargs)(x),
    resize=config_.partial_with_default_args(config_.resize, align_corners=False),
)

def create_x(input, convnext_variant, url, name=None):
    return_model = input is None
    if input is None:
        input = tf.keras.layers.Input((None, None, 3))

    x = input

    shortcut = partial(stochasticdepth.shortcut, drop_probability=0.0, scale_at_train_time=True)
    block = partial(convnext.block, shortcut=shortcut, factor=4)
    x = convnext_variant(x, block=block, name=join(name, "convnext"), config=config) # TODO: fix all pretrained model construction methods to take basename argument

    xs = [tfcv.model.graph.get_unique(x, pred=lambda layer: layer.name.endswith(f"block{i}")) for i in [1, 2, 3, 4]]
    xs = [norm(x, name=join(name, "neck", "norm", f"{i + 1}"), config=config) for i, x in enumerate(xs)]
    x = upernet.head(xs, filters=512, psp_bin_sizes=[1, 2, 3, 6], name=join(name, "head"), config=decoder_config)

    x = decode.decode(x, filters=150, shape=tf.shape(input)[1:-1], dropout=0.1, name=join(name, "decode"), config=decoder_config)
    x = tf.keras.layers.Softmax()(x)

    model = tf.keras.Model(inputs=[input], outputs=[x])

    weights = tf.keras.utils.get_file(url.split("/")[-1], url)
    tfcv.model.pretrained.weights.load_pth(weights, model, partial(convert_name, basename=name), ignore=lambda n: n.startswith("auxiliary") or "running" in n)

    return model if return_model else x

def make_builder(variant, url):
    class builder:
        @staticmethod
        def create(input=None, name=f"convnext_{variant}_upernet"):
            return create_x(
                input=input,
                convnext_variant=vars(convnext)[f"convnext_{variant}"],
                url=url,
                name=name,
            )

        preprocess = preprocess
        config = config
    return builder

class convnext_tiny_upernet_imagenet1k_ade20k_512(make_builder("tiny", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_tiny_1k_512x512.pth")): pass
class convnext_small_upernet_imagenet1k_ade20k_512(make_builder("small", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_small_1k_512x512.pth")): pass
class convnext_base_upernet_imagenet1k_ade20k_512(make_builder("base", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_base_1k_512x512.pth")): pass

class convnext_base_upernet_imagenet22k_ade20k_640(make_builder("base", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_base_22k_640x640.pth")): pass
class convnext_large_upernet_imagenet22k_ade20k_640(make_builder("large", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_large_22k_640x640.pth")): pass
class convnext_xlarge_upernet_imagenet22k_ade20k_640(make_builder("xlarge", f"https://dl.fbaipublicfiles.com/convnext/ade20k/upernet_convnext_xlarge_22k_640x640.pth")): pass
