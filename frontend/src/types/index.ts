export interface Plan {
  id: string;
  name: string;
  max_cameras: number | null;
  retention_days: number | null;
  email_alerts: boolean;
  realtime_alerts: boolean;
  price_monthly: number | string;
  is_active: boolean;
  ocr_engine: "system_default" | "easyocr" | "plate_recognizer";
  created_at: string;
  client_count?: number;
}

export interface OccurrenceWithCamera {
  id: string;
  plate: string;
  confidence: number;
  image_path: string;
  image_url: string;
  detected_at: string;
  expires_at: string | null;
  camera: CameraMin;
  vehicle_type: string | null;
  vehicle_color: string | null;
  vehicle_make_model: string | null;
  region_code: string | null;
  ocr_engine_used: string | null;
}

export interface Client {
  id: string;
  name: string;
  email: string;
  plan_id: string;
  plan_expires_at: string | null;
  is_active: boolean;
  created_at: string;
  plan?: Plan | null;
  camera_count: number;
}

export interface ClientCreateWithAdmin {
  name: string;
  email: string;
  plan_id: string;
  plan_expires_at?: string | null;
  is_active: boolean;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: "super_admin" | "client_admin" | "client_user";
  client_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Camera {
  id: string;
  client_id: string;
  name: string;
  location: string | null;
  connection_type: "rtsp" | "agent";
  rtsp_url: string | null;
  agent_token: string | null;
  dual_lens: boolean;
  lens_side: "upper" | "lower" | null;
  roi_x: number | null;
  roi_y: number | null;
  roi_width: number | null;
  roi_height: number | null;
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
  is_online: boolean;
  preview_fps: number;
  preview_frames_last_minute: number;
  preview_last_frame_at: string | null;
  preview_latency_seconds: number | null;
  preview_status: "offline" | "idle" | "streaming" | "degraded" | "stale";
  detector_status: "offline" | "idle" | "healthy" | "warning" | "degraded";
  detector_health_score: number;
  detector_status_detail: string;
  quality_score: number;
  quality_label: "unknown" | "excellent" | "good" | "fair" | "poor";
  blur_score: number;
  brightness: number;
  contrast: number;
}

export interface Occurrence {
  id: string;
  camera_id: string;
  plate: string;
  confidence: number;
  image_path: string | null;
  detected_at: string;
  expires_at: string | null;
  created_at: string;
}

export interface CameraMin {
  id: string;
  name: string;
  location: string | null;
}


export interface OccurrencePage {
  items: OccurrenceWithCamera[];
  total: number;
  page: number;
  pages: number;
}

export interface OccurrenceStats {
  total_today: number;
  total_week: number;
  top_cameras: { camera_id: string; camera_name: string; count: number }[];
  top_plates: { plate: string; count: number }[];
  by_hour: { hour: number; count: number }[];
}

export interface VehicleEventTypeCount {
  vehicle_type: string;
  count: number;
}

export interface TopVehicleCamera {
  camera_id: string;
  camera_name: string;
  count: number;
}

export interface VehicleHourBucket {
  hour: number;
  count: number;
}

export interface LatestVehicleEvent {
  id: string;
  camera_id: string;
  camera_name: string;
  camera_location: string | null;
  vehicle_type: string;
  confidence: number;
  detected_at: string;
}

export interface VehicleEventStats {
  total_today: number;
  total_week: number;
  by_type: VehicleEventTypeCount[];
  top_cameras: TopVehicleCamera[];
  by_hour: VehicleHourBucket[];
  latest_event: LatestVehicleEvent | null;
}

export interface MonitoredPlate {
  id: string;
  client_id: string;
  plate: string;
  description: string | null;
  alert_email: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AlertSent {
  id: string;
  occurrence_id: string;
  monitored_plate_id: string;
  channel: "email" | "websocket";
  sent_at: string;
  status: string;
}

export interface PlateAlert {
  type: "plate_alert";
  occurrence_id: string;
  plate: string;
  camera_name: string;
  location: string;
  detected_at: string;
  image_url: string;
  confidence: number;
}

export interface CameraHealthAlert {
  type: "camera_health_alert";
  client_id: string;
  camera_id: string;
  camera_name: string;
  location: string;
  detected_at: string;
  detector_status: "warning" | "degraded";
  detector_health_score: number;
  preview_status: "offline" | "idle" | "streaming" | "degraded" | "stale";
  quality_label: "unknown" | "excellent" | "good" | "fair" | "poor";
  detail: string;
}

export interface WorkerDelayAlert {
  type: "worker_delay_alert";
  detected_at: string;
  updated_at: number;
  queue_depth: number;
  threshold: number;
  detail: string;
}

export type RealtimeAlert = PlateAlert | CameraHealthAlert | WorkerDelayAlert;

export interface OperationalMetrics {
  total_cameras: number;
  online_cameras: number;
  streaming_cameras: number;
  degraded_cameras: number;
  low_quality_cameras: number;
  avg_preview_fps: number;
  avg_preview_latency_seconds: number | null;
  queue_depth: number;
  operational_status: "empty" | "offline" | "healthy" | "warning" | "degraded";
  operational_status_detail: string;
  generated_at: string;
}
