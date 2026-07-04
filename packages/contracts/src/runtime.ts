export type RuntimeState =
  | "booting"
  | "idle"
  | "listening"
  | "transcribing"
  | "analyzing"
  | "thinking"
  | "confirming"
  | "acting"
  | "synthesizing"
  | "speaking"
  | "interrupted"
  | "error";

export type VoiceAnalysisResult = {
  provider_id: string;
  status: string;
  language?: string;
  language_confidence?: number;
  sentiment?: string;
  emotion?: string;
  speaking_rate_wpm?: number;
  audio_quality?: string;
  warnings: string[];
};

export type AvatarPlaybackJob = {
  job_id: string;
  turn_id: string;
  avatar_id: string;
  audio_ref: string;
  mood: string;
  behavior: string;
  allow_interrupt: boolean;
  visemes: Array<{ time_ms: number; name: string; weight: number }>;
};

