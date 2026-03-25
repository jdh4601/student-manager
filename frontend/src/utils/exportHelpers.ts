import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import type { GradeItem, Subject } from '../types';

export function exportGradesToExcel(
  subjects: Subject[],
  grades: GradeItem[],
  studentName: string,
) {
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
  XLSX.writeFile(wb, `${studentName}_성적.xlsx`);
}

export function exportGradesToPDF(
  subjects: Subject[],
  grades: GradeItem[],
  studentName: string,
) {
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
  doc.save(`${studentName}_성적.pdf`);
}
