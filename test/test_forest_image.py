import unittest
import bokeh.models
import forest.image
import numpy as np


class TestForestImage(unittest.TestCase):
    """Test suite to test server side image tools

    .. note:: forestjs is where CustomJS callback
              code is unit tested
    """
    def setUp(self):
        self.empty_image = bokeh.models.ColumnDataSource({
            "image": []
        })

    def test_can_be_constructed(self):
        slider = forest.image.Slider(self.empty_image, self.empty_image)

    def test_slider_should_react_to_left_image_shape_change(self):
        """Forest sometimes changes the rgba array shape

        To avoid this situation there should be a listener
        keeping the _shapes array consistent
        """
        old_pixels = np.zeros((100, 100, 4))
        new_pixels = np.zeros((10, 10, 4))
        image = bokeh.models.ColumnDataSource({
            "image": [old_pixels]
        })
        slider = forest.image.Slider(image, self.empty_image)
        image.data["image"] = [new_pixels]
        # self.assertEqual(image.data["_shape"], [new_pixels.shape])

    def test_slider_should_react_to_right_image_shape_change(self):
        """Forest sometimes changes the rgba array shape

        To avoid this situation there should be a listener
        keeping the _shapes array consistent
        """
        old_pixels = np.zeros((100, 100, 4))
        new_pixels = np.zeros((10, 10, 4))
        image = bokeh.models.ColumnDataSource({
            "image": [old_pixels]
        })
        slider = forest.image.Slider(self.empty_image, image)
        image.data["image"] = [new_pixels]
        self.assertEqual(image.data["_shape"], [new_pixels.shape])


class TestToggle(unittest.TestCase):
    """Toggle to make left/right images switchable"""
    def setUp(self):
        self.empty_image = bokeh.models.ColumnDataSource({})

    def test_consistent_alpha(self):
        """data source image shape change should be handled gracefully"""
        small_rgba = np.zeros((2, 2, 4))
        large_rgba = np.zeros((10, 10, 4))
        large_alpha = large_rgba[..., -1]
        image = bokeh.models.ColumnDataSource({
            "image": [small_rgba]
        })
        toggle = forest.image.Toggle(image, self.empty_image)
        toggle.hide(toggle.left_images)

        # Simulate Forest resizing image data
        image.data = {
            "image": [large_rgba]
        }

        # Assertions
        np.testing.assert_array_equal(image.data["_alpha"][0], large_alpha)
