"""
Grid overlay for AI vision analysis.
Adds a 9x9 reference grid with chess-style labels (A-I, 1-9).

Based on Grid-Augmented Vision research (arXiv:2411.18270)
- 9x9 grid, black lines, 0.3 alpha = optimal for spatial understanding

Ported from ~/ops/aston/scripts/grid_overlay.py
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64


# Prompt prefix to explain the grid overlay to vision LLMs
GRID_PROMPT_PREFIX = """This screenshot has a reference grid overlay (NOT part of the UI).
The grid divides the image into a 9x9 matrix labeled A-I (columns) and 1-9 (rows).
Use coordinates like "B3" or "F7" to reference specific locations.
Ignore the grid and white border when evaluating the UI design.

"""


def get_ux_review_prompt(focus_areas: list[str] = None) -> str:
    """
    Generate a complete prompt for UX screenshot review.

    Args:
        focus_areas: Optional list of specific areas to check.
                    Defaults to common UX issues.

    Returns:
        Complete prompt string with grid explanation.
    """
    if focus_areas is None:
        focus_areas = [
            "Misaligned or inconsistently spaced elements",
            "Text truncation, overflow, or label issues",
            "Visual hierarchy problems",
            "Inconsistent padding or margins",
            "Accessibility concerns (contrast, touch target size)",
            "Broken or placeholder content",
        ]

    checks = "\n".join(f"- {area}" for area in focus_areas)

    return f"""{GRID_PROMPT_PREFIX}Review this app screenshot for UX issues. For each issue found:
1. State the grid coordinate (e.g., "C4")
2. Describe the problem
3. Suggest a fix

Check for:
{checks}

If no issues are found in a category, skip it. Be specific and actionable."""


def add_reference_grid(
    img: Image.Image,
    grid_size: int = 9,
    alpha: float = 0.3,
    margin: int = 15,
    line_width: int = 1,
) -> Image.Image:
    """
    Add a reference grid with chess-style labels to an image.

    Args:
        img: Input PIL Image
        grid_size: Number of grid divisions (default 9 for A-I, 1-9)
        alpha: Grid line transparency (0.3 recommended)
        margin: White border size in pixels for labels
        line_width: Grid line thickness

    Returns:
        New image with grid overlay and labels
    """
    orig_w, orig_h = img.size

    # Create new canvas with white margins
    new_w = orig_w + (margin * 2)
    new_h = orig_h + (margin * 2)
    canvas = Image.new('RGBA', (new_w, new_h), (255, 255, 255, 255))

    # Paste original image centered
    canvas.paste(img.convert('RGBA'), (margin, margin))

    # Create overlay for grid lines
    overlay = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    line_color = (0, 0, 0, int(255 * alpha))

    # Draw vertical lines (extend into margins)
    for i in range(grid_size + 1):
        x = margin + (orig_w * i // grid_size)
        draw.line([(x, 0), (x, new_h)], fill=line_color, width=line_width)

    # Draw horizontal lines (extend into margins)
    for i in range(grid_size + 1):
        y = margin + (orig_h * i // grid_size)
        draw.line([(0, y), (new_w, y)], fill=line_color, width=line_width)

    # Composite grid onto canvas
    canvas = Image.alpha_composite(canvas, overlay)

    # Draw labels
    label_draw = ImageDraw.Draw(canvas)

    # Try to get a small font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except (IOError, OSError):
        font = ImageFont.load_default()

    label_color = (80, 80, 80, 255)  # Dark gray for readability

    # Column labels (A-I) - centered in each cell
    col_labels = [chr(ord('A') + i) for i in range(grid_size)]
    for i, label in enumerate(col_labels):
        cell_center_x = margin + (orig_w * i // grid_size) + (orig_w // grid_size // 2)

        # Top label
        bbox = label_draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        label_draw.text(
            (cell_center_x - text_w // 2, 2),
            label, fill=label_color, font=font
        )

        # Bottom label
        label_draw.text(
            (cell_center_x - text_w // 2, new_h - margin + 3),
            label, fill=label_color, font=font
        )

    # Row labels (1-9) - centered in each cell
    row_labels = [str(i + 1) for i in range(grid_size)]
    for i, label in enumerate(row_labels):
        cell_center_y = margin + (orig_h * i // grid_size) + (orig_h // grid_size // 2)

        bbox = label_draw.textbbox((0, 0), label, font=font)
        text_h = bbox[3] - bbox[1]

        # Left label
        label_draw.text(
            (4, cell_center_y - text_h // 2),
            label, fill=label_color, font=font
        )

        # Right label
        label_draw.text(
            (new_w - margin + 4, cell_center_y - text_h // 2),
            label, fill=label_color, font=font
        )

    return canvas


def process_base64(
    image_base64: str,
    grid_size: int = 9,
    alpha: float = 0.3,
    margin: int = 15,
    output_format: str = "png",
) -> str:
    """
    Process a base64-encoded image and return the result as base64.

    Args:
        image_base64: Base64-encoded input image
        grid_size: Number of grid divisions (default 9)
        alpha: Grid line transparency (0.3 recommended)
        margin: White border size in pixels for labels
        output_format: Output image format (png, jpeg)

    Returns:
        Base64-encoded output image
    """
    # Decode input
    image_data = base64.b64decode(image_base64)
    img = Image.open(BytesIO(image_data))

    # Process
    result = add_reference_grid(img, grid_size=grid_size, alpha=alpha, margin=margin)

    # Convert to RGB if saving as JPEG
    if output_format.lower() in ['jpg', 'jpeg']:
        result = result.convert('RGB')

    # Encode output
    buffer = BytesIO()
    result.save(buffer, format=output_format.upper())
    return base64.b64encode(buffer.getvalue()).decode('utf-8')
