import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../api/classes', () => ({
  listClasses: vi.fn(async () => [
    { id: 'c1', name: '1반', grade: 3, year: 2025, teacher_id: 't1' },
  ]),
}));

vi.mock('../../hooks/useStudents', () => ({
  useStudents: () => ({
    data: [
      { id: 's1', name: '김철수', student_number: 1 },
      { id: 's2', name: '이영희', student_number: 2 },
    ],
    isLoading: false,
  }),
}));

const studentsExcelSpy = vi.fn().mockResolvedValue(undefined);
vi.mock('../../utils/exportHelpers', () => ({
  exportStudentsToExcel: (...args: any[]) => studentsExcelSpy(...args),
}));

import StudentListPage from '../../pages/StudentListPage';

describe('StudentListPage', () => {
  it('exports current class students to Excel', async () => {
    const user = userEvent.setup();
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <StudentListPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const exportBtn = screen.getByRole('button', { name: 'Excel로 내보내기' });
    await waitFor(() => expect(exportBtn).toBeEnabled());

    await user.click(exportBtn);
    expect(studentsExcelSpy).toHaveBeenCalledTimes(1);
  });

  it('enables add and upload buttons when classes load', async () => {
    const user = userEvent.setup();
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <StudentListPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const addBtn = await screen.findByRole('button', { name: '학생 추가' });
    const uploadBtn = await screen.findByRole('button', { name: '엑셀로 등록' });
    await waitFor(() => {
      expect(addBtn).toBeEnabled();
      expect(uploadBtn).toBeEnabled();
    });

    // Clicking should open modals; close buttons should appear
    await user.click(addBtn);
    expect(await screen.findByRole('heading', { name: '학생 추가' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '×' }));

    await user.click(uploadBtn);
    expect(await screen.findByRole('heading', { name: '학생 엑셀 업로드' })).toBeInTheDocument();
  });
});
