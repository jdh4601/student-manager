import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  getPreferences,
  listNotifications,
  markAllRead,
  markRead,
  NotificationItem,
  type NotificationPreferences,
  updatePreferences,
} from '../api/notifications';
import { useAuthStore } from '../stores/authStore';
import { Card, CardHeader } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';

const NOTIFICATION_LABELS: Record<string, string> = {
  grade_input: '성적 입력',
  feedback_created: '피드백',
  counseling_updated: '상담',
};

const GENERATED_NAME_SUFFIX_RE = /-notify-\d{10,}-[a-z0-9]+$/i;
const PAGE_SIZE = 5;

function cleanEntityLabel(value: string): string {
  return value.replace(GENERATED_NAME_SUFFIX_RE, '').trim().replace(/[\s-]+$/g, '');
}

function formatNotificationMessage(notification: NotificationItem): string {
  const raw = notification.message?.trim();
  if (!raw) return '알림 내용을 확인해 주세요.';

  const gradeMatch = raw.match(/^(.*?)의 (.*?) 성적이 저장되었습니다\.$/);
  if (gradeMatch) {
    return `${cleanEntityLabel(gradeMatch[1])} · ${cleanEntityLabel(gradeMatch[2])} 성적이 저장되었어요.`;
  }

  const feedbackMatch = raw.match(/^(.*?) 피드백이 등록되었습니다\.$/);
  if (feedbackMatch) {
    return `${cleanEntityLabel(feedbackMatch[1])} · 새 피드백이 등록되었어요.`;
  }

  const counselingMatch = raw.match(/^(.*?) 상담 기록이 업데이트되었습니다\.$/);
  if (counselingMatch) {
    return `${cleanEntityLabel(counselingMatch[1])} · 상담 기록이 업데이트되었어요.`;
  }

  return cleanEntityLabel(raw);
}

export default function NotificationsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const role = useAuthStore((state) => state.user?.role);
  const [currentPage, setCurrentPage] = useState(1);

  const { data } = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => listNotifications(),
  });

  const { data: preferences } = useQuery({
    queryKey: ['notifications', 'preferences'],
    queryFn: () => getPreferences(),
  });
  const [draftPreferences, setDraftPreferences] = useState<NotificationPreferences | null>(null);

  useEffect(() => {
    if (preferences) {
      setDraftPreferences(preferences);
    }
  }, [preferences]);

  const markOne = useMutation({
    mutationFn: (id: string) => markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications', 'list'] });
      qc.invalidateQueries({ queryKey: ['notifications', 'unread'] });
    },
  });

  const markAll = useMutation({
    mutationFn: () => markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications', 'list'] });
      qc.invalidateQueries({ queryKey: ['notifications', 'unread'] });
    },
  });

  const savePreferences = useMutation({
    mutationFn: updatePreferences,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications', 'preferences'] });
    },
  });

  const togglePreference = (key: keyof NotificationPreferences) => {
    setDraftPreferences((current) => {
      if (!current) return current;
      return { ...current, [key]: !current[key] };
    });
  };

  const visibleNotifications = useMemo(() => {
    if (!data) return [];
    if (!draftPreferences) return data;

    return data.filter((notification) => {
      if (notification.type === 'grade_input') return draftPreferences.grade_input;
      if (notification.type === 'feedback_created') return draftPreferences.feedback_created;
      if (notification.type === 'counseling_updated') return draftPreferences.counseling_updated;
      return true;
    });
  }, [data, draftPreferences]);

  const totalPages = Math.max(1, Math.ceil(visibleNotifications.length / PAGE_SIZE));

  useEffect(() => {
    setCurrentPage(1);
  }, [draftPreferences?.grade_input, draftPreferences?.feedback_created, draftPreferences?.counseling_updated]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const paginatedNotifications = useMemo(() => {
    const startIndex = (currentPage - 1) * PAGE_SIZE;
    return visibleNotifications.slice(startIndex, startIndex + PAGE_SIZE);
  }, [currentPage, visibleNotifications]);

  const openNotification = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      await markOne.mutateAsync(notification.id);
    }

    if (role === 'teacher') {
      if (notification.type === 'grade_input' && notification.related_id) {
        navigate(`/grades/${notification.related_id}`);
        return;
      }
      if (notification.type === 'counseling_updated' && notification.related_id) {
        navigate(`/counselings?studentId=${notification.related_id}`);
        return;
      }
      if (notification.type === 'feedback_created' && notification.related_id) {
        navigate(`/students/${notification.related_id}`);
        return;
      }
    }

    if (role === 'student') {
      navigate('/student');
      return;
    }
    if (role === 'parent') {
      navigate('/parent');
      return;
    }

    navigate('/notifications');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">알림</h1>
          <p className="mt-1 text-sm text-ink-soft">성적·피드백·상담 활동 알림을 확인하세요.</p>
        </div>
        <Button variant="ghost" size="md" onClick={() => markAll.mutate()}>전체 읽음 처리</Button>
      </div>

      {draftPreferences && (
        <Card>
          <CardHeader title="알림 설정" subtitle="설정을 끄면 새 알림 수신이 중단되고, 현재 목록에서도 해당 유형이 숨겨집니다." />
          <div className="mt-4 space-y-3">
            <label className="flex items-center gap-2 text-sm text-ink" htmlFor="notification-grade-input">
              <input
                id="notification-grade-input"
                type="checkbox"
                className="h-4 w-4 accent-clay"
                checked={draftPreferences.grade_input}
                onChange={() => togglePreference('grade_input')}
              />
              성적 입력 알림
            </label>
            <label className="flex items-center gap-2 text-sm text-ink" htmlFor="notification-feedback-created">
              <input
                id="notification-feedback-created"
                type="checkbox"
                className="h-4 w-4 accent-clay"
                checked={draftPreferences.feedback_created}
                onChange={() => togglePreference('feedback_created')}
              />
              피드백 알림
            </label>
            <label className="flex items-center gap-2 text-sm text-ink" htmlFor="notification-counseling-updated">
              <input
                id="notification-counseling-updated"
                type="checkbox"
                className="h-4 w-4 accent-clay"
                checked={draftPreferences.counseling_updated}
                onChange={() => togglePreference('counseling_updated')}
              />
              상담 알림
            </label>
            <div className="flex justify-end">
              <Button variant="primary" onClick={() => draftPreferences && savePreferences.mutate(draftPreferences)}>
                설정 저장
              </Button>
            </div>
          </div>
        </Card>
      )}

      {(!data || data.length === 0) ? (
        <Card className="text-center text-muted">
          <p className="text-lg text-ink-soft">알림이 없습니다</p>
          <p className="mt-1 text-sm">새로운 알림이 오면 여기에 표시됩니다.</p>
        </Card>
      ) : visibleNotifications.length === 0 ? (
        <Card className="text-center text-muted">
          <p className="text-lg text-ink-soft">현재 설정으로 표시할 알림이 없어요</p>
          <p className="mt-1 text-sm">알림 설정을 다시 켜면 숨겨진 알림을 바로 볼 수 있습니다.</p>
        </Card>
      ) : (
        <Card flush className="flex h-[36rem] flex-col p-5 sm:p-6">
          <ul className="flex-1 space-y-2 overflow-y-auto pr-1">
            {paginatedNotifications.map((notification) => (
              <li
                key={notification.id}
                className={`rounded-xl border border-line p-3 transition-colors ${notification.is_read ? 'opacity-60' : 'bg-clay-wash/30'}`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant={notification.is_read ? 'neutral' : 'accent'}>
                    {NOTIFICATION_LABELS[notification.type] ?? '알림'}
                  </Badge>
                  <span className="text-xs text-muted">{new Date(notification.created_at).toLocaleString()}</span>
                </div>
                <div className="mt-1.5 text-sm text-ink">{formatNotificationMessage(notification)}</div>
                <div className="mt-1.5 flex items-center gap-3 text-xs font-medium text-clay-ink">
                  {!notification.is_read && (
                    <button className="hover:underline" onClick={() => markOne.mutate(notification.id)}>읽음</button>
                  )}
                  <button className="hover:underline" onClick={() => openNotification(notification)}>관련 화면으로 이동</button>
                </div>
              </li>
            ))}
          </ul>
          {visibleNotifications.length > PAGE_SIZE && (
            <div className="flex items-center justify-center gap-3 pt-4">
              <button
                type="button"
                aria-label="이전 페이지"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface text-sm text-ink transition-colors hover:bg-surface-soft disabled:cursor-not-allowed disabled:opacity-40"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              >
                ←
              </button>
              <span className="text-sm text-ink-soft">{currentPage} / {totalPages}</span>
              <button
                type="button"
                aria-label="다음 페이지"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface text-sm text-ink transition-colors hover:bg-surface-soft disabled:cursor-not-allowed disabled:opacity-40"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
              >
                →
              </button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
