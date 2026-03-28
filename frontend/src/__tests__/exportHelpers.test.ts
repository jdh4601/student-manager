import { describe, it, expect, vi, beforeEach } from 'vitest';

import type { GradeItem, Subject, StudentSummary } from '../types';

const { writeFileSpy, saveSpy } = vi.hoisted(() => ({
  writeFileSpy: vi.fn(),
  saveSpy: vi.fn(),
}));

// Mock xlsx dynamic import
vi.mock('xlsx', () => ({
  utils: {
    json_to_sheet: vi.fn(() => ({} as any)),
    book_new: vi.fn(() => ({} as any)),
    book_append_sheet: vi.fn(),
  },
  writeFile: (...args: any[]) => writeFileSpy(...args),
}));

// Mock jsPDF dynamic import
vi.mock('jspdf', () => {
  class MockJsPDF {
    setFontSize() {}
    text() {}
    save(name: string) {
      saveSpy(name);
    }
  }
  return { default: MockJsPDF };
});

// Import after mocks so dynamic imports use our stubs
import {
  exportGradesToExcel,
  exportGradesToPDF,
  exportStudentsToExcel,
} from '../utils/exportHelpers';

describe('exportHelpers', () => {
  beforeEach(() => {
    writeFileSpy.mockClear();
    saveSpy.mockClear();
  });

  it('exports grades to Excel with sanitized filename', async () => {
    const subjects: Subject[] = [
      { id: 'sub1', name: '국어', class_id: 'c1' },
      { id: 'sub2', name: '수학', class_id: 'c1' },
    ];
    const grades: GradeItem[] = [
      { id: 'g1', student_id: 's1', subject_id: 'sub1', semester_id: 'sem1', score: 95, grade_rank: 2 },
      { id: 'g2', student_id: 's1', subject_id: 'sub2', semester_id: 'sem1', score: 88, grade_rank: 3 },
    ];

    await exportGradesToExcel(subjects, grades, '홍 길/동');

    expect(writeFileSpy).toHaveBeenCalled();
    const filename = writeFileSpy.mock.calls[0][1] as string;
    expect(filename).toContain('홍_길_동_성적.xlsx');
  });

  it('exports grades to PDF with sanitized filename', async () => {
    const subjects: Subject[] = [{ id: 'sub1', name: '과학', class_id: 'c1' }];
    const grades: GradeItem[] = [
      { id: 'g1', student_id: 's1', subject_id: 'sub1', semester_id: 'sem1', score: 77, grade_rank: 3 },
    ];

    await exportGradesToPDF(subjects, grades, '테/스 트');

    expect(saveSpy).toHaveBeenCalled();
    const filename = saveSpy.mock.calls[0][0] as string;
    expect(filename).toContain('테_스_트_성적.pdf');
  });

  it('exports students to Excel with class label when provided', async () => {
    const students: StudentSummary[] = [
      { id: 's1', user_id: 'u1', class_id: 'c1', name: '김철수', student_number: 3 },
      { id: 's2', user_id: 'u2', class_id: 'c1', name: '이영희', student_number: 1 },
    ];

    await exportStudentsToExcel(students, '2025학년도# 3학년/1반');

    expect(writeFileSpy).toHaveBeenCalled();
    const filename = writeFileSpy.mock.calls[0][1] as string;
    expect(filename).toContain('2025학년도__3학년_1반_학생목록.xlsx');
  });
});
