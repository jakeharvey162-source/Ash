"""Intentional visual directions, inspired by open design-system patterns.

These are original prompts and tokens. No third-party premium source code is
embedded or copied. Installing a registry component needs a separate reviewed
build action and its actual upstream license.
"""
from __future__ import annotations

DESIGN_PRESETS = {
    "editorial-luxe": {
        "label": "Editorial Luxe",
        "direction": "Editorial art direction with premium typography, asymmetric bento grids, generous whitespace, and distinctive image crops.",
        "palette": ["#10141B", "#F5F1EA", "#B89360", "#526477"],
        "type": "Contrasting display serif headlines with clean readable sans-serif body",
        "motion": "Restrained reveal on entry with reduced-motion alternative",
    },
    "midnight-studio": {
        "label": "Midnight Studio",
        "direction": "Sophisticated near-black product studio, bright selective accents, large typography, fine hairline dividers and purposeful glow.",
        "palette": ["#0A0C12", "#EAEFF7", "#8FE4CF", "#4B596C"],
        "type": "Modern geometric sans-serif with clear numeric hierarchy",
        "motion": "Subtle hover lift and focused transition, never constant distracting animation",
    },
    "warm-commerce": {
        "label": "Warm Commerce",
        "direction": "Inviting premium storefront, photography-first, editorial product cards, trustworthy checkout and elegant filtering.",
        "palette": ["#F7F3E9", "#332A24", "#D9754A", "#7C8B66"],
        "type": "Expressive display headline and legible humanist sans-serif",
        "motion": "Product transitions and feedback with accessible low-motion fallback",
    },
    "clean-enterprise": {
        "label": "Clean Enterprise",
        "direction": "Credible modern SaaS visual language: precise data tables, calm layered surfaces, clear sidebar navigation and practical forms.",
        "palette": ["#F7F9FC", "#17263A", "#3976DF", "#E2E8F0"],
        "type": "Neutral highly readable sans-serif with tabular numerals",
        "motion": "Only functional micro-interactions, focus feedback and loading skeletons",
    },
}
DESIGN_LIBRARIES = [
    {"name": "shadcn/ui", "repo": "https://github.com/shadcn-ui/ui", "license": "MIT", "role": "accessible customizable primitives"},
    {"name": "Magic UI", "repo": "https://github.com/magicuidesign/magicui", "license": "check each item upstream", "role": "optional premium motion and bento effects"},
    {"name": "Aceternity UI", "repo": "https://ui.aceternity.com", "license": "separate Aceternity terms", "role": "optional visual references; do not redistribute premium code"},
    {"name": "Motion", "repo": "https://github.com/motiondivision/motion", "license": "check repository before installation", "role": "optional accessible motion"},
]
QUALITY_GATES = (
    "Responsive at 360, 390, 768 and 1440px with no horizontal overflow.",
    "Functional main navigation, hover/focus states, keyboard navigation and forms with validation.",
    "Original copy relevant to the user's actual business; no invented awards, clients or reviews.",
    "Explicit visual hierarchy, consistent 8px spacing scale, readable contrast and semantic HTML.",
    "Respect prefers-reduced-motion, show real loading/empty/error states.",
    "Use real component packages only when installed and the resulting build passes; never invent imports.",
    "Run the actual build and browser visual tests before claiming the result is production-ready.",
)

def design_spec(preset: str) -> tuple[str, dict]:
    if preset not in DESIGN_PRESETS:
        raise ValueError("Unsupported Ash design preset")
    data = DESIGN_PRESETS[preset]
    prompt = (
        "PREMIUM PRODUCT DESIGN BRIEF (original implementation; no copied third-party premium components):\n"
        f"Preset: {data['label']}\n"
        f"Direction: {data['direction']}\n"
        f"Palette suggestions: {', '.join(data['palette'])}\n"
        f"Typography: {data['type']}\n"
        f"Motion: {data['motion']}\n"
        "Use the principles of accessible shadcn/ui-style design where appropriate. "
        "If a component library is not an installed dependency, create valid original components instead.\n"
        "REQUIRED ACCEPTANCE:\n- " + "\n- ".join(QUALITY_GATES)
    )
    return prompt, {"design_preset": preset, "design_label": data["label"],
                    "suggested_colors": data["palette"], "component_libraries_installed": False}
