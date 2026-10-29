"""自有 Smart Serial 型号表；HAL 路径使用实测原文，不猜测大小写。"""
import re

MODELS = {
    "SD01": {"label": "SD01 智能串口 MPG 板", "inputs": 16, "outputs": 16,
             "encoder": True, "upgrade_board_id": 1},
    "SD02": {"label": "SD02 智能串口 IO 板", "inputs": 16, "outputs": 16,
             "encoder": False, "upgrade_board_id": 2},
}


def identify_hal_pin(pin):
    """识别实际 HAL 引脚名称。7i69 无法唯一判断硬件，必须另行核对。"""
    match = re.fullmatch(r"(hm2_[A-Za-z0-9_]+\.\d+)\.([A-Za-z0-9]{4})\.(\d+)\.(\d+)\.(.+)", pin)
    if not match:
        return None
    host, short, port, channel, field = match.groups()
    model = MODELS.get(short.upper())
    if model is None:
        return None
    prefix = f"{host}.{short}.{port}.{channel}"
    return {**model, "model": short.upper(), "hal_prefix": prefix, "field": field}


def rename_selected_remote(text, old_prefix, new_prefix):
    """迁移用户指定的一块从板；不全局替换所有7i69、不写原文件。"""
    pattern = r"hm2_[A-Za-z0-9_]+\.\d+\.[A-Za-z0-9]{4}\.\d+\.\d+"
    if not re.fullmatch(pattern, old_prefix) or not re.fullmatch(pattern, new_prefix):
        raise ValueError("需要完整、已核对的从板 HAL 前缀")
    return re.sub(r"(?<![\w.])" + re.escape(old_prefix) + r"(?=\.)", new_prefix, text)
