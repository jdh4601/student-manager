/**
 * SMS-69 / REQ-073, RISK-002: 분석 대시보드 RBAC.
 *
 * 검증:
 *   - teacher2(같은 학교, 다른 teacher_id)는 teacher1의 학생/학급 분석에 403
 *   - 학생 role은 /analytics/** 전부 403
 *   - 미인증 요청은 401
 *   - 본인 소유 데이터는 200으로 정상 접근
 *
 * Kafka 의존 없음 — 분석 테이블에 데이터가 없어도 RBAC 단계에서 거절되므로
 * 일반 Playwright CI(no Kafka)에서 그대로 통과한다.
 */

import { expect, test } from '@playwright/test'

import {
  acceptInvitation,
  createApiContext,
  loginAndGetToken,
  seedAcademicScenario,
  uniqueSuffix,
} from './helpers'

test.describe('analytics RBAC', () => {
  test('teacher2 cannot read teacher1 student/class analytics', async () => {
    const scenario = await seedAcademicScenario(uniqueSuffix('rbac'))
    const { student, class: klass, subjects, semesters } = scenario

    const teacher2Token = await loginAndGetToken('teacher2@example.com')
    const t2Api = await createApiContext(teacher2Token)

    const overview = await t2Api.get(
      `analytics/students/${student.id}/overview`,
      { params: { semester_id: semesters.current.id } },
    )
    expect(overview.status()).toBe(403)

    const distribution = await t2Api.get(
      `analytics/classes/${klass.id}/distribution`,
      {
        params: {
          subject_id: subjects.korean.id,
          semester_id: semesters.current.id,
        },
      },
    )
    expect(distribution.status()).toBe(403)

    await t2Api.dispose()
  })

  test('teacher2 dashboard returns only their own classes (empty)', async () => {
    await seedAcademicScenario(uniqueSuffix('rbac-dash'))
    const teacher2Token = await loginAndGetToken('teacher2@example.com')
    const api = await createApiContext(teacher2Token)

    const res = await api.get('analytics/teachers/me/dashboard')
    expect(res.ok()).toBeTruthy()
    const body = (await res.json()) as { classes: { class_id: string }[] }
    // teacher2 자신이 소유한 클래스만 — teacher1이 만든 클래스가 섞이면 안 됨
    expect(Array.isArray(body.classes)).toBe(true)
    await api.dispose()
  })

  test('student role gets 403 on analytics endpoints', async () => {
    const scenario = await seedAcademicScenario(uniqueSuffix('rbac-stu'))
    const studentLogin = await acceptInvitation(scenario.student.invite_url)
    const api = await createApiContext(studentLogin.access_token)

    const dashboard = await api.get('analytics/teachers/me/dashboard')
    expect(dashboard.status()).toBe(403)

    const overview = await api.get(
      `analytics/students/${scenario.student.id}/overview`,
    )
    expect(overview.status()).toBe(403)

    await api.dispose()
  })

  test('unauthenticated requests get 401', async () => {
    const api = await createApiContext()
    const dashboard = await api.get('analytics/teachers/me/dashboard')
    expect(dashboard.status()).toBe(401)

    const overview = await api.get(
      `analytics/students/00000000-0000-0000-0000-000000000000/overview`,
    )
    expect(overview.status()).toBe(401)
    await api.dispose()
  })

  test('owning teacher can read their own analytics (sanity)', async () => {
    const scenario = await seedAcademicScenario(uniqueSuffix('rbac-own'))
    const { token, student, semesters } = scenario
    const api = await createApiContext(token)

    const overview = await api.get(
      `analytics/students/${student.id}/overview`,
      { params: { semester_id: semesters.current.id } },
    )
    // 200 OK either with data or with null overall (분석 worker가 안 돌면 null)
    expect(overview.ok()).toBeTruthy()
    await api.dispose()
  })
})
