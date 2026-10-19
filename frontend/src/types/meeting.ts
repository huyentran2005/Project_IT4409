export interface MeetingDraft {
  title: string
  date: string
  startTime: string
  endTime: string
  location: string
  meetingUrl: string
  description: string
}

export interface Meeting extends MeetingDraft {
  id: string
  projectId: string
}
