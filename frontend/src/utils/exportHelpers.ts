import type { GradeItem, Subject, StudentSummary } from '../types';

// Sanitize names used in filenames to prevent path traversal / special char issues
function safeName(name: string): string {
  return name.replace(/[^a-zA-Z0-9가-힣_-]/g, '_');
}

export async function exportGradesToExcel(
  subjects: Subject[],
  grades: GradeItem[],
  studentName: string,
) {
  const XLSX = await import('xlsx');
  const gradeMap = new Map(grades.map((g) => [g.subject_id, g]));
  const rows = subjects.map((s) => {
    const g = gradeMap.get(s.id);
    return {
      과목: s.name,
      점수: g?.score ?? '',
      등급: g?.grade_rank ?? '',
    };
  });
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '성적');
  XLSX.writeFile(wb, `${safeName(studentName)}_성적.xlsx`);
}

export async function exportGradesToPDF(
  subjects: Subject[],
  grades: GradeItem[],
  studentName: string,
) {
  const { default: jsPDF } = await import('jspdf');
  const doc = new jsPDF();
  doc.setFontSize(16);
  doc.text(`${studentName} 성적표`, 14, 20);

  const gradeMap = new Map(grades.map((g) => [g.subject_id, g]));
  let y = 36;
  doc.setFontSize(11);
  subjects.forEach((s) => {
    const g = gradeMap.get(s.id);
    doc.text(`${s.name}: ${g?.score ?? '-'} (등급 ${g?.grade_rank ?? '-'})`, 14, y);
    y += 8;
  });
  doc.save(`${safeName(studentName)}_성적.pdf`);
}

export async function exportStudentsToExcel(students: StudentSummary[], classLabel?: string) {
  const XLSX = await import('xlsx');
  const rows = students
    .slice()
    .sort((a, b) => a.student_number - b.student_number)
    .map((s) => ({ 번호: s.student_number, 이름: s.name, 학생ID: s.id }));
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '학생목록');
  const filename = classLabel
    ? `${safeName(classLabel)}_학생목록.xlsx`
    : `학생목록.xlsx`;
  XLSX.writeFile(wb, filename);
}
