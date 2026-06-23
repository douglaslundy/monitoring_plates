"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, ImageOff } from "lucide-react";
import api from "@/lib/api";

export interface Roi {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface PixelRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface RoiSelectorProps {
  cameraId: string | null;
  /** No cadastro (sem cameraId): captura um frame da RTSP digitada. */
  rtspUrl?: string | null;
  dualLens?: boolean;
  lensSide?: string | null;
  initial?: Roi | null;
  onConfirm: (roi: Roi) => void;
  onCancel: () => void;
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

/**
 * Exibe um frame atual da câmera (latest.jpg) e deixa o admin desenhar a área
 * (ROI) que a câmera deve analisar. Ao confirmar, devolve a ROI em frações 0..1.
 * Precisa de um frame disponível — câmera salva e conectada.
 */
export function RoiSelector({ cameraId, rtspUrl, dualLens, lensSide, initial, onConfirm, onCancel }: RoiSelectorProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const [rect, setRect] = useState<PixelRect | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [src, setSrc] = useState<string>("");

  const hasSource = Boolean(cameraId || (rtspUrl && rtspUrl.trim()));

  function revokeBlob() {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
  }

  const reload = useCallback(() => {
    setRect(null);
    setLoaded(false);
    setError(false);
    revokeBlob();
    setCapturing(true);
    if (cameraId) {
      // Câmera existente: busca snapshot autenticado (latest.jpg ou captura ao vivo).
      api
        .get(`/api/cameras/${cameraId}/snapshot`, { responseType: "blob" })
        .then((r) => {
          const url = URL.createObjectURL(r.data as Blob);
          blobUrlRef.current = url;
          setSrc(url);
        })
        .catch(() => setError(true))
        .finally(() => setCapturing(false));
      return;
    }
    if (rtspUrl && rtspUrl.trim()) {
      // Cadastro: captura um frame da RTSP digitada via backend.
      api
        .post(
          "/api/cameras/preview-frame",
          { rtsp_url: rtspUrl.trim(), dual_lens: Boolean(dualLens), lens_side: lensSide ?? null },
          { responseType: "blob" }
        )
        .then((r) => {
          const url = URL.createObjectURL(r.data as Blob);
          blobUrlRef.current = url;
          setSrc(url);
        })
        .catch(() => setError(true))
        .finally(() => setCapturing(false));
    } else {
      setCapturing(false);
    }
  }, [cameraId, rtspUrl, dualLens, lensSide]);

  useEffect(() => {
    reload();
    return () => revokeBlob();
  }, [reload]);

  // Converte a ROI inicial (frações) em pixels quando a imagem carrega.
  function handleLoaded() {
    setLoaded(true);
    setError(false);
    const img = imgRef.current;
    if (img && initial && initial.width > 0 && initial.height > 0) {
      setRect({
        left: initial.x * img.clientWidth,
        top: initial.y * img.clientHeight,
        width: initial.width * img.clientWidth,
        height: initial.height * img.clientHeight,
      });
    }
  }

  function pointerPos(e: React.MouseEvent): { x: number; y: number } {
    const img = imgRef.current!;
    const b = img.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(b.width, e.clientX - b.left)),
      y: Math.max(0, Math.min(b.height, e.clientY - b.top)),
    };
  }

  function onMouseDown(e: React.MouseEvent) {
    if (!loaded) return;
    e.preventDefault();
    const p = pointerPos(e);
    setStart(p);
    setDrawing(true);
    setRect({ left: p.x, top: p.y, width: 0, height: 0 });
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!drawing || !start) return;
    const p = pointerPos(e);
    setRect({
      left: Math.min(start.x, p.x),
      top: Math.min(start.y, p.y),
      width: Math.abs(p.x - start.x),
      height: Math.abs(p.y - start.y),
    });
  }

  function onMouseUp() {
    setDrawing(false);
  }

  function confirm() {
    const img = imgRef.current;
    if (!img || !rect || rect.width < 4 || rect.height < 4) return;
    const W = img.clientWidth;
    const H = img.clientHeight;
    if (W <= 0 || H <= 0) return;
    let x = clamp01(rect.left / W);
    let y = clamp01(rect.top / H);
    let width = clamp01(rect.width / W);
    let height = clamp01(rect.height / H);
    // Garante caber no frame.
    width = Math.min(width, 1 - x);
    height = Math.min(height, 1 - y);
    onConfirm({
      x: Number(x.toFixed(4)),
      y: Number(y.toFixed(4)),
      width: Number(width.toFixed(4)),
      height: Number(height.toFixed(4)),
    });
  }

  if (!hasSource) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Para o preview, informe a URL RTSP da câmera (no cadastro) ou salve a câmera
          e aguarde a conexão. Câmeras por agente: o preview aparece após o 1º frame.
        </p>
        <div className="flex justify-end">
          <button onClick={onCancel} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">
            Fechar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Arraste sobre a imagem para selecionar a área que a câmera deve analisar.
        </p>
        <button
          type="button"
          onClick={reload}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 border rounded-lg text-xs hover:bg-gray-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Atualizar frame
        </button>
      </div>

      <div
        ref={wrapRef}
        className="relative inline-block max-w-full select-none bg-black/5 rounded-lg overflow-hidden"
      >
        {error ? (
          <div className="flex flex-col items-center justify-center gap-2 p-10 text-muted-foreground">
            <ImageOff className="h-10 w-10 opacity-40" />
            <p className="text-sm">Não foi possível obter um frame. Verifique a URL/conexão da câmera.</p>
          </div>
        ) : capturing ? (
          <div className="flex flex-col items-center justify-center gap-2 p-10 text-muted-foreground">
            <RefreshCw className="h-8 w-8 animate-spin opacity-50" />
            <p className="text-sm">Capturando frame da câmera…</p>
          </div>
        ) : (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={src}
              alt="Preview da câmera"
              onLoad={handleLoaded}
              onError={() => setError(true)}
              className="block max-w-full h-auto"
              draggable={false}
            />
            <div
              className="absolute inset-0 cursor-crosshair"
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={onMouseUp}
            >
              {rect && rect.width > 0 && rect.height > 0 && (
                <div
                  className="absolute border-2 border-yellow-400 bg-yellow-400/20 pointer-events-none"
                  style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}
                />
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        <button onClick={onCancel} className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">
          Cancelar
        </button>
        <button
          onClick={confirm}
          disabled={!loaded || !rect || rect.width < 4 || rect.height < 4}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          Usar esta área
        </button>
      </div>
    </div>
  );
}
