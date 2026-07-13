import os
import cv2
import albumentations as A

INPUT_DIR = "~/untamperedImages"       # Path to the original images
OUTPUT_DIR = "~/augmentedImages"   # Path to save generated images
NUM_AUGMENTATIONS = 5              


augmentation_pipeline = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.Rotate(limit=15, p=0.8),
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.8),
    A.GaussNoise(var_limit=(0.02, 0.05), p=0.3), # Adds noise for robustness
])


os.makedirs(OUTPUT_DIR, exist_ok=True)


supported_extensions = ('.jpg', '.jpeg', '.png')
for filename in os.listdir(INPUT_DIR):
    if filename.lower().endswith(supported_extensions):
        image_path = os.path.join(INPUT_DIR, filename)
        
        # Load image (Albumentations works with OpenCV's BGR format)
        image = cv2.imread(image_path)
        
        if image is None:
            continue
            
        base_name, ext = os.path.splitext(filename)
        
        # Generate the specified number of augmentations
        for i in range(NUM_AUGMENTATIONS):
            augmented = augmentation_pipeline(image=image)
            augmented_image = augmented['image']
            
            # Save the augmented image
            output_filename = f"{base_name}_aug_{i}{ext}"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            cv2.imwrite(output_path, augmented_image)

print(f"Augmentation complete! Check the '{OUTPUT_DIR}' folder.")
