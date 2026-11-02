#!/bin/bash
# 草稿（本地版）启动器
# 双击本文件：启动本地服务（静态页面 + Python 运行接口），
# 并以独立窗口（Chrome 应用模式，无标签栏）打开页面
# 数据仅保存在本机浏览器 localStorage，不联网上传

PORT=8765
URL="http://127.0.0.1:$PORT/"
cd "$(dirname "$0")"

# 该端口专用于本工具：先停掉可能在跑的旧版服务，再启动最新后端
lsof -ti :"$PORT" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null
sleep 0.3
nohup python3 server.py >/dev/null 2>&1 &
sleep 0.6

# 优先 Chrome 应用模式独立窗口；无 Chrome 用 Edge；都没有退回默认浏览器新窗口
BROWSER=""
if [ -d "/Applications/Google Chrome.app" ]; then
  BROWSER="Google Chrome"
  open -na "Google Chrome" --args --app="$URL"
elif [ -d "/Applications/Microsoft Edge.app" ]; then
  BROWSER="Microsoft Edge"
  open -na "Microsoft Edge" --args --app="$URL"
else
  open -n "$URL"
fi

# 独立窗口默认设为当前屏幕的 5/16 大小（宽高各 62.5%的屏一半，置于左上角）
if [ -n "$BROWSER" ]; then
  # 取主屏逻辑尺寸（单位与窗口坐标一致）
  SCREEN=$(osascript -l JavaScript -e 'ObjC.import("CoreGraphics"); var r = $.CGDisplayBounds($.CGMainDisplayID()); r.size.width + "," + r.size.height' 2>/dev/null)
  if [ -n "$SCREEN" ]; then
    SW=$(echo "$SCREEN" | awk -F',' '{print int($1)}')
    SH=$(echo "$SCREEN" | awk -F',' '{print int($2)}')
    W2=$((SW * 5 / 16))
    H2=$((SH * 5 / 16))
    TOP=25   # 菜单栏高度
    # 等窗口出现后设置尺寸（最多重试 10 次，每次 0.3 秒）
    for i in $(seq 1 10); do
      if osascript -e "tell application \"$BROWSER\" to set bounds of front window to {0, $TOP, $W2, $((TOP + H2))}" 2>/dev/null; then
        break
      fi
      sleep 0.3
    done
  fi
fi
exit 0
