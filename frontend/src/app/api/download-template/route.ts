import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy endpoint for downloading SD templates.
 * This avoids CORS issues by fetching from the backend server-side.
 * 
 * Usage: GET /api/download-template?filename=1%20ДУИС.DOCX
 */
export async function GET(request: NextRequest) {
  const filename = request.nextUrl.searchParams.get("filename");

  if (!filename) {
    return NextResponse.json({ error: "Missing filename parameter" }, { status: 400 });
  }

  // Backend URL from Docker internal network or fallback
  const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
  const url = `${backendUrl}/api/templates-sd/download/${encodeURIComponent(filename)}`;

  try {
    const res = await fetch(url);

    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }

    const blob = await res.blob();
    const buffer = Buffer.from(await blob.arrayBuffer());

    // RFC 5987 encoding for Cyrillic filenames
    const encodedFilename = encodeURIComponent(filename).replace(/%20/g, "+");

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodedFilename}`,
        "Content-Length": String(buffer.length),
      },
    });
  } catch (err: any) {
    console.error("Template download proxy error:", err);
    return NextResponse.json(
      { error: "Failed to fetch template from backend" },
      { status: 502 }
    );
  }
}
