"""Bot pricing and fee management"""

BOT_PRICING = {
    "momentum": 19.49,
    "dca": 7.49,
    "grid": 7.49,
    "infinity": 7.49,
    "all_bots": 25.49
}

def get_bot_fee(bot_type: str) -> float:
    """Get the fee for a specific bot type"""
    normalized_type = bot_type.lower()
    return BOT_PRICING.get(normalized_type, 0.0)

def get_bot_display_name(bot_type: str) -> str:
    """Get display name for bot type"""
    names = {
        "momentum": "Momentum Bot",
        "dca": "DCA Bot",
        "grid": "Grid Bot",
        "infinity": "Infinity Bot",
        "all_bots": "All Bots Bundle"
    }
    return names.get(bot_type.lower(), bot_type)
