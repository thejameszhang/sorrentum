import logging

# TODO(*): Disabled because of PartTask186.
#import gluonts
#import gluonts.dataset.artificial.recipe as gdar  # isort: skip # noqa: F401 # pylint: disable=unused-import
#import mxnet
#import pandas as pd
#
#import core.artificial_signal_generators as sig_gen
#import helpers.printing as prnt
#import helpers.unit_test as hut
#
#_LOG = logging.getLogger(__name__)
#
#
#class TestGenerateRecipeDataset(hut.TestCase):
#    def test1(self) -> None:
#        mxnet.random.seed(0, ctx="all")
#        recipe = [
#            (
#                "feat_dynamic_real",
#                gluonts.dataset.artificial.recipe.SmoothSeasonality(
#                    period=288, phase=-72
#                ),
#            ),
#            (
#                "noise",
#                gluonts.dataset.artificial.recipe.RandomGaussian(
#                    shape=[0], stddev=0.1
#                ),
#            ),
#            (
#                "target",
#                gluonts.dataset.artificial.recipe.Add(
#                    inputs=["feat_dynamic_real", "noise"]
#                ),
#            ),
#            (
#                "feat_dynamic_real",
#                gluonts.dataset.artificial.recipe.RandomGaussian(shape=(1, 0)),
#            ),
#            # What GluonTS does is find zeros in shape and replace them
#            # with length.
#        ]
#        train_dataset = sig_gen.generate_recipe_dataset(
#            recipe, "D", pd.Timestamp("2010-01-01"), 100, 10, 1
#        )
#        train_str = str(list(train_dataset.train))
#        test_str = str(list(train_dataset.test))
#        self.check_string(
#            f"{prnt.frame('train')}{train_str}\n"
#            f"{prnt.frame('test')}{test_str}"
#        )
