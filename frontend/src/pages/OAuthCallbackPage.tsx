import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { oauthGoogleCallback, getMe } from '../api/auth';
import { useAuthStore } from '../stores/authStore';

/**
 * Google OAuth 리다이렉트 착지점.
 * Google(또는 stub)이 `?code=...`로 돌려보내면 백엔드와 code를 교환해
 * 토큰을 받고 세션을 확립한 뒤 홈으로 이동한다.
 */
export default function OAuthCallbackPage() {
  const [error, setError] = useState<string | null>(null);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const navigate = useNavigate();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // StrictMode 이중 실행 방지
    ran.current = true;

    const code = new URLSearchParams(window.location.search).get('code');
    if (!code) {
      setError('인증 코드가 없습니다.');
      return;
    }

    (async () => {
      try {
        const tok = await oauthGoogleCallback(code);
        setAccessToken(tok.access_token);
        setUser(await getMe());
        navigate('/', { replace: true });
      } catch (e: any) {
        const detail = e?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Google 로그인에 실패했습니다.');
      }
    })();
  }, [navigate, setAccessToken, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white p-6 rounded shadow w-full max-w-md text-center space-y-3">
        {error ? (
          <>
            <div className="text-red-600 text-sm" role="alert">{error}</div>
            <button onClick={() => navigate('/login')} className="text-blue-600 hover:underline text-sm">
              로그인으로 돌아가기
            </button>
          </>
        ) : (
          <div className="text-gray-600 text-sm">Google 계정으로 로그인 중...</div>
        )}
      </div>
    </div>
  );
}
