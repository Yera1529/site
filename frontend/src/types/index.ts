export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "lawyer";
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Matter {
  id: string;
  name: string;
  description: string | null;
  custom_instructions: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatterListItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  file_count: number;
}

export interface FileItem {
  id: string;
  matter_id: string;
  original_name: string;
  file_type: string;
  file_size: number;
  uploaded_at: string;
}

export interface ChatMessage {
  id: string;
  matter_id: string;
  user_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface Template {
  id: string;
  name: string;
  description: string | null;
  file_type: string;
  file_size: number;
  extracted_text: string | null;
  created_at: string;
}

export interface KBDocument {
  id: string;
  filename: string;
  title: string;
  article: string;
  chunk_count: number;
  file_size: number;
  created_at: string;
}

export interface KBStats {
  total_documents: number;
  total_chunks: number;
}

export interface AppSetting {
  key: string;
  value: string;
}

export interface LegislationDoc {
  id: string;
  title: string;
  category: string;
  year: number | null;
  filename: string;
  article_count: number;
  chunk_count: number;
  file_size: number;
  file_type: string;
  indexed_at: string | null;
  created_at: string;
}

export interface LegislationDetail extends LegislationDoc {
  content: string;
}

export interface ArticleNode {
  number: string;
  title: string;
  text: string;
}

export interface RetrievedLaw {
  text: string;
  law_title: string;
  article_number: string;
  category: string;
  score: number;
}

export interface CitationCheck {
  cited: string[];
  unverified: string[];
}

export interface RepresentationItem {
  id: string;
  matter_id: string;
  template_id: string | null;
  title: string;
  content: string;
  status: "draft" | "finalized" | "sent";
  selected_law_ids: string;
  validation_result: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
