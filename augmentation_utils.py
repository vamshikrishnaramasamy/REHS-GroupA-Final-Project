import albumentations as A

NUM_AUGMENTATIONS = 6

augmentation_pipeline = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.5),
    A.Rotate(limit=15, p=0.8),
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.8),
    A.GaussNoise(std_range=(0.02, 0.05), p=0.3),  # Adds noise for robustness
])


def generate_variants(image, count=NUM_AUGMENTATIONS):
    """Run the shared augmentation pipeline over a BGR image array `count` times."""
    return [augmentation_pipeline(image=image)["image"] for _ in range(count)]
