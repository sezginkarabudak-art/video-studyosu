"""Local, free FFmpeg visual-effect presets for Video Studyosu.

The module only returns allow-listed filter expressions. It does not execute
commands, download models, or require network/API access.
"""
VIDEO_EFFECT_PRESETS = {
    "Kapalı": "",
    "Sinematik": "eq=contrast=1.12:saturation=0.92:gamma=0.98,colorbalance=rs=-0.03:bs=0.04,vignette=angle=PI/5,noise=alls=3:allf=t+u",
    "Korku": "eq=contrast=1.24:saturation=0.70:brightness=-0.035,colorbalance=rs=0.04:gs=-0.02:bs=0.08,vignette=angle=PI/4,noise=alls=5:allf=t+u",
    "Vintage": "eq=contrast=1.08:saturation=0.78,colorbalance=rs=0.06:gs=0.02:bs=-0.05,vignette=angle=PI/4,noise=alls=8:allf=t+u",
    "Siyah-beyaz": "hue=s=0,eq=contrast=1.16:brightness=0.01,vignette=angle=PI/5",
    "Rüya": "gblur=sigma=1.1,eq=brightness=0.025:saturation=1.12:gamma=1.04",
    "Keskin ve canlı": "unsharp=5:5:0.8:3:3:0.35,eq=contrast=1.08:saturation=1.06",
}


def get_video_effect_filter(name):
    """Return a known filter chain, or an empty string for unknown/disabled names."""
    return VIDEO_EFFECT_PRESETS.get(str(name or "Kapalı"), "")
