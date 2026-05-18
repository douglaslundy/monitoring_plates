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
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
  is_online: boolean;
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
