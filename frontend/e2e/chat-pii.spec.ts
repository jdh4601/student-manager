/**
 * SMS-70 / REQ-082, RISK-007: 챗봇 PII 차단.
 *
 * - k<5 학급: 응답이 정중한 거부 메시지("5명 미만 …") 여야 함
 * - k≥5 학급: 응답에 RAW 학생명/학번이 노출되지 않아야 함
 *
 * 백엔드는 stub LLM provider(`LLM_PROVIDER=auto` 이고 `OPENAI_API_KEY` 미설정 시)로
 * 동작하므로 외부 의존성 없이 일반 CI에서 그린.
 */

import { expect, test } from '@playwright/test'

import {
  createApiContext,
  createClass,
  createStudentAccount,
  loginAndGetToken,
  uniqueSuffix,
} from './helpers'

async function postChat(token: string, message: string) {
  const api = await createApiContext(token)
  const res = await api.post('chat', { data: { message } })
  expect(res.ok()).toBeTruthy()
  const body = (await res.json()) as {
    thread_id: string
    reply: string
    referenced_students: { id: string; name: string }[]
  }
  await api.dispose()
  return body
}

async function cleanupTeacherClasses(token: string) {
  const api = await createApiContext(token)
  const list = await api.get('classes')
  if (list.ok()) {
    const classes = (await list.json()) as { id: string }[]
    for (const c of classes) {
      await api.delete(`classes/${c.id}`, { params: { force: 'true' } })
    }
  }
  await api.dispose()
}

async function seedStudents(token: string, count: number) {
  const suffix = uniqueSuffix('pii')
  const klass = await createClass(token, `${suffix}-반`, 1)
  const names: string[] = []
  for (let i = 1; i <= count; i++) {
    const name = `철수${suffix}-${i}`
    await createStudentAccount(token, {
      email: `${suffix}-${i}@example.com`,
      name,
      classId: klass.id,
      studentNumber: i,
      birthDate: '2010-03-02',
    })
    names.push(name)
  }
  return { suffix, klass, names }
}

test.describe.serial('chat PII k-anonymity', () => {
  test.beforeEach(async () => {
    // 전 테스트에서 누적된 클래스/학생 제거 — chat은 teacher 전체 학생을 컨텍스트로 쓰므로
    // k 계산을 결정론적으로 만들려면 매 테스트에 깨끗한 상태에서 시작해야 함.
    const token = await loginAndGetToken('teacher2@example.com')
    await cleanupTeacherClasses(token)
  })

  test('k<5: refusal message, no statistics', async () => {
    const token = await loginAndGetToken('teacher2@example.com')
    const { names } = await seedStudents(token, 4)

    const reply = await postChat(token, '이번 학기 평균 좀 알려줘')

    expect(reply.reply).toContain('5명 미만')
    expect(reply.referenced_students).toEqual([])
    for (const name of names) {
      expect(reply.reply).not.toContain(name)
    }
  })

  test('k≥5: response masks raw student names', async () => {
    const token = await loginAndGetToken('teacher2@example.com')
    const { names } = await seedStudents(token, 5)

    const reply = await postChat(token, '평균 분포 분석해줘')

    // 거부 메시지가 아니어야 함
    expect(reply.reply).not.toContain('5명 미만')

    // RAW 학생명이 응답 텍스트에 노출되지 않아야 함
    for (const name of names) {
      expect(
        reply.reply,
        `raw student name "${name}" leaked into reply`,
      ).not.toContain(name)
    }

    // 학번도 노출되지 않아야 함 — seq_NNN 마스킹은 OK
    const numberPattern = /(?<!seq_)\b\d{4,}\b/
    expect(numberPattern.test(reply.reply)).toBeFalsy()
  })
})
