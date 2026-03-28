import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadGradesXlsx, uploadStudentsXlsx } from '../api/imports';

export function useUploadStudents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { classId: string; file: Blob }) => {
      return uploadStudentsXlsx(args.classId, args.file);
    },
    onSuccess: (_data, variables) => {
      // Invalidate students list for this class
      qc.invalidateQueries({ queryKey: ['students', { classId: variables.classId }] });
    },
  });
}

export function useUploadGrades() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { classId: string; semesterId: string; file: Blob }) => {
      return uploadGradesXlsx(args.classId, args.semesterId, args.file);
    },
    onSuccess: (_data, variables) => {
      // No specific cache key here; pages should refetch grades if necessary
      qc.invalidateQueries();
    },
  });
}

