import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login, getMe, oauthGoogleLogin } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();
  const params = new URLSearchParams(window.location.search);
  const reason = useMemo(() => params.get('reason'), [params.toString()]);

  // In dev, ask password managers to ignore to avoid buggy overlays
  const pmIgnore = import.meta.env.MODE !== 'production';
  const pmAttrs = pmIgnore
    ? ({ 'data-bwignore': 'true', 'data-1p-ignore': 'true', 'data-lpignore': 'true' } as const)
    : ({} as const);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Basic validation
    const emailTrim = email.trim();
    const passwordTrim = password.trim();
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailTrim);
    if (!emailTrim || !emailValid) {
      setError('유효한 이메일 주소를 입력하세요.');
      return;
    }
    if (!passwordTrim) {
      setError('비밀번호를 입력하세요.');
      return;
    }

    setLoading(true);
    try {
      const tok = await login(emailTrim, passwordTrim);
      setAccessToken(tok.access_token);
      const me = await getMe();
      setUser(me);
      navigate('/');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let message = '이메일 또는 비밀번호가 올바르지 않습니다.';
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail)) {
        // Pydantic v2 validation errors
        const msgs = detail.map((d: any) => d?.msg).filter(Boolean);
        if (msgs.length > 0) message = msgs.join(', ');
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <form onSubmit={onSubmit} autoComplete="on" {...pmAttrs} className="bg-white p-6 rounded shadow w-full max-w-md space-y-4">
        <div className="text-center">
          <div className="text-2xl font-bold">ClassFlow</div>
          <div className="text-sm text-gray-500 mt-1">다시 오신 것을 환영합니다. 계속하려면 로그인하세요.</div>
        </div>

        {reason === 'expired' && (
          <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
            세션이 만료되었습니다. 다시 로그인해주세요.
          </div>
        )}
        {error && <div className="text-red-600 text-sm" role="alert">{error}</div>}

        <div>
          <label htmlFor="email" className="block text-sm text-gray-700 mb-1">이메일</label>
          <input
            id="email"
            className="border p-2 w-full rounded"
            placeholder="이메일"
            type="email"
            name="email"
            autoComplete="username email"
            required
            {...pmAttrs}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm text-gray-700 mb-1">비밀번호</label>
          <input
            id="password"
            className="border p-2 w-full rounded"
            placeholder="비밀번호"
            type="password"
            name="password"
            autoComplete="current-password"
            required
            {...pmAttrs}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-500">세션은 보안 쿠키로만 유지됩니다.</div>
          <Link to="/forgot-password" className="text-sm text-blue-600 hover:underline">비밀번호를 잊으셨나요?</Link>
        </div>

        <button
          className="bg-blue-600 text-white p-2 rounded w-full disabled:opacity-60"
          type="submit"
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? '로그인 중...' : '로그인'}
        </button>

        <div className="relative py-1">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
          <div className="relative flex justify-center"><span className="bg-white px-2 text-xs text-gray-400">교사</span></div>
        </div>

        <button
          type="button"
          onClick={async () => {
            setError(null);
            try {
              const { authorize_url } = await oauthGoogleLogin();
              window.location.href = authorize_url;
            } catch {
              setError('Google 로그인을 시작할 수 없습니다.');
            }
          }}
          className="border border-gray-300 text-gray-700 p-2 rounded w-full hover:bg-gray-50"
        >
          Google로 로그인 (학교 이메일)
        </button>

        <div className="text-center text-sm text-gray-600">
          초대 링크가 있으신가요?{' '}
          <Link to="/signup" className="text-blue-600 hover:underline">초대 수락</Link>
        </div>
      </form>
    </div>
  );
}
