/** Typed client for /api/v1/analytics. */
import api from '@/services/api'
import type { ID } from '@/types'
import type {
  AtRiskList,
  ClassAnalytics,
  DashboardOverview,
  ExamListItem,
  ExamSummary,
  StudentTrend,
  SubjectAnalytics,
} from '@/types/analytics'

function sectionParams(classSectionIds?: readonly ID[]): { class_section_ids?: string } {
  return classSectionIds && classSectionIds.length > 0 ? { class_section_ids: classSectionIds.join(',') } : {}
}

export const analyticsService = {
  async overview(): Promise<DashboardOverview> {
    const { data } = await api.get<DashboardOverview>('/analytics/overview')
    return data
  },

  async listExams(): Promise<ExamListItem[]> {
    const { data } = await api.get<ExamListItem[]>('/analytics/exams')
    return data
  },

  async examSummary(examId: ID, classSectionIds?: readonly ID[]): Promise<ExamSummary> {
    const { data } = await api.get<ExamSummary>(`/analytics/exams/${examId}/summary`, {
      params: sectionParams(classSectionIds),
    })
    return data
  },

  async examClass(examId: ID, classId: ID): Promise<ClassAnalytics> {
    const { data } = await api.get<ClassAnalytics>(`/analytics/exams/${examId}/classes/${classId}`)
    return data
  },

  async examSubject(examId: ID, subjectId: ID, classSectionIds?: readonly ID[]): Promise<SubjectAnalytics> {
    const { data } = await api.get<SubjectAnalytics>(`/analytics/exams/${examId}/subjects/${subjectId}`, {
      params: sectionParams(classSectionIds),
    })
    return data
  },

  async atRisk(examId: ID, classSectionIds?: readonly ID[]): Promise<AtRiskList> {
    const { data } = await api.get<AtRiskList>(`/analytics/exams/${examId}/at-risk`, {
      params: sectionParams(classSectionIds),
    })
    return data
  },

  async studentTrend(studentId: ID): Promise<StudentTrend> {
    const { data } = await api.get<StudentTrend>(`/analytics/students/${studentId}/trend`)
    return data
  },
}
