.PHONY: install test web demo record cov

install:
	pip install -r requirements.txt

test:
	pytest

cov:
	pytest --cov-report=html && echo "open htmlcov/index.html"

web:        ## 离线模式启动 Web（无需 VPN）
	STORY2SCRIPT_AI_BACKEND=offline python -m story2script.app

demo: web   ## 等同 web，便于演示

record:     ## 录制离线 fixture（需公司内网/VPN）：make record NOVEL=samples/story.txt
	python -m story2script.tools.record $(NOVEL)
