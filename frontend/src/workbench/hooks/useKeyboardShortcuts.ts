import { useEffect } from 'react';
import { useReviewStore, computeEffectiveChanges } from '../store/useReviewStore';

/**
 * 全局键盘快捷键（spec 第七节）：
 * J/K 上一条/下一条 · Enter 确认当前字段 · Cmd/Ctrl+Enter 提交
 * Cmd/Ctrl+S 暂存 · Alt+↓ 跳到下一个异常 · Esc 关闭弹窗/退出编辑
 */
export function useKeyboardShortcuts() {
  useEffect(() => {
    function isFormEl(t: EventTarget | null): boolean {
      const el = t as HTMLElement | null;
      if (!el) return false;
      const tag = el.tagName;
      return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
    }

    function onKey(e: KeyboardEvent) {
      const st = useReviewStore.getState();
      const mod = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl + S 暂存
      if (mod && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        st.stash();
        return;
      }

      // Cmd/Ctrl + Enter 提交审核
      if (mod && e.key === 'Enter') {
        e.preventDefault();
        if (st.ticket && !st.submitDialogOpen) {
          const changes = computeEffectiveChanges(st.ticket, st.fieldStates, st.changeLog);
          st.openSubmitDialog(changes.length > 0 ? 'approved_with_changes' : 'approved');
        }
        return;
      }

      // Esc 关闭弹窗 / 退出编辑
      if (e.key === 'Escape') {
        if (st.submitDialogOpen) {
          st.closeSubmitDialog();
          return;
        }
        if (st.conflict) return; // 冲突弹窗需明确选择，不靠 Esc 关闭
        if (st.editingFieldId) {
          st.setEditingField(null);
          return;
        }
        return;
      }

      // Alt + ↓ 跳到下一个异常
      if (e.altKey && e.key === 'ArrowDown') {
        e.preventDefault();
        st.jumpToNextAnomaly();
        return;
      }

      // 在表单元素内：仅 Enter(input) 确认当前编辑字段，其余不拦截
      if (isFormEl(e.target)) {
        if (
          e.key === 'Enter' &&
          st.editingFieldId &&
          (e.target as HTMLElement).tagName === 'INPUT'
        ) {
          e.preventDefault();
          st.confirmField(st.editingFieldId);
        }
        return;
      }

      // 全局：J/K 翻页，Enter 确认
      if (e.key === 'j' || e.key === 'J') {
        e.preventDefault();
        st.nextTicket();
      } else if (e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        st.prevTicket();
      } else if (e.key === 'Enter' && st.editingFieldId) {
        e.preventDefault();
        st.confirmField(st.editingFieldId);
      }
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
}
