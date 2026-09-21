"""防护领用「开放」状态的唯一判定口径。

轮灌新建拦截、温室列表的开放标记、开放核对统计都从这里取数，
保证任何入口看到的开放状态一致（拦截与领用状态共用判定）。
"""

from .models import PpeIssue


def open_ppe_issues():
    """所有处于开放状态的防护领用单。"""
    return PpeIssue.objects.filter(status=PpeIssue.STATUS_OPEN)


def greenhouse_has_open_ppe_issue(greenhouse_id):
    """指定温室当前是否存在开放的防护领用单。"""
    return open_ppe_issues().filter(greenhouse_id=greenhouse_id).exists()


def open_ppe_issue_greenhouse_ids():
    """存在开放防护领用单的温室 id 集合（去重）。"""
    return open_ppe_issues().values_list("greenhouse_id", flat=True).distinct()
