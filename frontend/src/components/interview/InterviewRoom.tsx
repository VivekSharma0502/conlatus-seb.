"use client";

import { motion } from "framer-motion";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Microphone,
  MicrophoneSlash,
  VideoCamera,
  VideoCameraSlash,
  MonitorArrowUp,
  ChatCircleText,
  Clock,
  CheckCircle,
  Spinner,
  PaperPlaneRight,
  SignOut,
  User,
} from "@phosphor-icons/react";
import SpecularButton from "../SpecularButton";
import SpecularContainer from "../SpecularContainer";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface InterviewRoomProps {
  interviewId: string;
  candidateName?: string;
  candidateEmail?: string;
  initialRoleTitle?: string;
  initialCompanyName?: string;
  durationMinutes?: number;
  token?: string;
  onExit?: () => void;
}

export default function InterviewRoom({
  interviewId,
  candidateName = "Candidate",
  candidateEmail,
  initialRoleTitle = "Software Engineer Interview",
  initialCompanyName = "Acme Corp",
  durationMinutes = 30,
  token,
  onExit,
}: InterviewRoomProps) {
  const [isMicOn, setIsMicOn] = useState(false);
  const [isVideoOn, setIsVideoOn] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roleTitle, setRoleTitle] = useState<string>(initialRoleTitle);
  const [companyName, setCompanyName] = useState<string>(initialCompanyName);
  const [currentQuestion, setCurrentQuestion] = useState<string>("");
  const [transcript, setTranscript] = useState<{ role: string; content: string }[]>([]);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [typedMessage, setTypedMessage] = useState("");

  const audioChunks = useRef<Blob[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Helper to get auth header with candidate JWT token
  const getAuthHeaders = useCallback((): HeadersInit => {
    let activeToken = token;
    if (!activeToken && typeof window !== "undefined") {
      activeToken = localStorage.getItem("interview_token");
      if (!activeToken) {
        const match = document.cookie.match(new RegExp("(^| )candidate_token=([^;]+)")) ||
                      document.cookie.match(new RegExp("(^| )auth_token=([^;]+)"));
        if (match) activeToken = match[2];
      }
    }
    return {
      ...(activeToken ? { Authorization: `Bearer ${activeToken}` } : {}),
    };
  }, [token]);

  const speakText = (text: string) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  useEffect(() => {
    if (transcriptEndRef.current) {
      transcriptEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [transcript, isProcessing]);

  // Timer interval
  useEffect(() => {
    if (!sessionId || isCompleted) return;
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [sessionId, isCompleted]);

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // Start interview session with backend
  useEffect(() => {
    const startInterview = async () => {
      if (!interviewId) return;
      try {
        const headers: HeadersInit = {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        };

        const res = await fetch(`${API_BASE_URL}/interview/start`, {
          method: "POST",
          headers,
          referrerPolicy: "unsafe-url",
          body: JSON.stringify({
            interview_id: interviewId,
            candidate_id: candidateEmail || "candidate-web",
          }),
        });

        if (!res.ok) {
          throw new Error("Failed to start session");
        }

        const data = await res.json();
        setSessionId(data.session_id);
        if (data.role_title) setRoleTitle(`${data.role_title} Interview`);
        if (data.company_name) setCompanyName(data.company_name);
        setCurrentQuestion(data.question);
        setTranscript([{ role: "interviewer", content: data.question }]);
        speakText(data.question);
      } catch (err) {
        console.error("Failed to start interview:", err);
      }
    };

    if (interviewId && !sessionId) {
      startInterview();
    }
  }, [interviewId, sessionId, candidateEmail, getAuthHeaders]);

  const toggleMedia = async (type: "audio" | "video") => {
    try {
      const newMicState = type === "audio" ? !isMicOn : isMicOn;
      const newVideoState = type === "video" ? !isVideoOn : isVideoOn;

      // If both are turning off, stop all tracks
      if (!newMicState && !newVideoState) {
        if (stream) {
          stream.getTracks().forEach((track) => track.stop());
          setStream(null);
        }
        setIsMicOn(false);
        setIsVideoOn(false);
        return;
      }

      // Request new stream with desired tracks
      const newStream = await navigator.mediaDevices.getUserMedia({
        video: newVideoState,
        audio: newMicState,
      });

      // Stop old tracks to avoid orphaned streams
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }

      setStream(newStream);
      if (type === "audio") setIsMicOn(!isMicOn);
      if (type === "video") setIsVideoOn(!isVideoOn);
    } catch (err) {
      console.error("Error accessing media devices.", err);
      alert("Unable to access microphone/camera. Please check your browser permissions.");
    }
  };

  const handlePushToTalkStart = useCallback(() => {
    if (isCompleted) {
      alert("This interview has concluded. Thank you!");
      return;
    }
    if (!stream || !sessionId) {
      toggleMedia("audio");
      return;
    }

    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      alert("No active microphone track found. Please turn on your microphone.");
      return;
    }
    const audioStream = new MediaStream(audioTracks);

    try {
      const mr = new MediaRecorder(audioStream);
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };
      mr.onstop = async () => {
        const actualType = mr.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunks.current, { type: actualType });
        audioChunks.current = [];

        if (audioBlob.size < 500) {
          console.warn("Audio recording was too short.");
          return;
        }

        const ext = actualType.includes("mp4") ? "mp4" : actualType.includes("ogg") ? "ogg" : "webm";
        const formData = new FormData();
        formData.append("file", audioBlob, `audio.${ext}`);

        setIsProcessing(true);
        try {
          const headers = getAuthHeaders();
          const res = await fetch(`${API_BASE_URL}/interview/${sessionId}/audio-message`, {
            method: "POST",
            headers,
            referrerPolicy: "unsafe-url",
            body: formData,
          });

          if (!res.ok) {
            const errJson = await res.json().catch(() => ({ detail: "Failed to process audio" }));
            console.error("Backend error:", errJson);
            if (errJson.detail && (errJson.detail.includes("ended") || errJson.detail.includes("completed"))) {
              setIsCompleted(true);
              const finishText = "Thank you for completing the interview! Your responses have been recorded.";
              setCurrentQuestion("Interview Completed");
              setTranscript((prev) => [...prev, { role: "interviewer", content: finishText }]);
              speakText(finishText);
            } else {
              alert(errJson.detail || "Audio was not recognized clearly. Please try speaking again.");
            }
            return;
          }

          const data = await res.json();
          if (data.transcript) {
            setTranscript((prev) => [
              ...prev,
              { role: "candidate", content: data.transcript },
              ...(data.next_question ? [{ role: "interviewer", content: data.next_question }] : []),
            ]);
          }

          if (data.next_question) {
            setCurrentQuestion(data.next_question);
            speakText(data.next_question);
          } else if (data.status === "completed" || data.status === "length_limited") {
            setIsCompleted(true);
            const conclusionMsg =
              "Thank you for taking the time to interview with us! We have recorded all your responses and completed the evaluation.";
            setCurrentQuestion("Interview Completed");
            setTranscript((prev) => [...prev, { role: "interviewer", content: conclusionMsg }]);
            speakText(conclusionMsg);
          }
        } catch (err) {
          console.error("Failed to send audio message:", err);
          alert("Network error communicating with the interview server. Please retry.");
        } finally {
          setIsProcessing(false);
        }
      };
      audioChunks.current = [];
      mr.start();
      setMediaRecorder(mr);
      setIsRecording(true);
    } catch (e) {
      console.error("Failed to start MediaRecorder:", e);
      alert("Microphone recording failed to initialize. Please refresh the page.");
    }
  }, [stream, sessionId, isCompleted, getAuthHeaders]);

  const handlePushToTalkStop = useCallback(() => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      setIsRecording(false);
    }
  }, [mediaRecorder]);

  // Typed response submission fallback
  const handleSendTextMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedMessage.trim() || !sessionId || isProcessing || isCompleted) return;

    const messageText = typedMessage.trim();
    setTypedMessage("");
    setTranscript((prev) => [...prev, { role: "candidate", content: messageText }]);
    setIsProcessing(true);

    try {
      const headers: HeadersInit = {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      };

      const res = await fetch(`${API_BASE_URL}/interview/${sessionId}/message`, {
        method: "POST",
        headers,
        referrerPolicy: "unsafe-url",
        body: JSON.stringify({ message: messageText }),
      });

      if (!res.ok) {
        throw new Error("Failed to send response");
      }

      const data = await res.json();
      if (data.next_question) {
        setCurrentQuestion(data.next_question);
        setTranscript((prev) => [...prev, { role: "interviewer", content: data.next_question }]);
        speakText(data.next_question);
      } else if (data.status === "completed" || data.status === "length_limited") {
        setIsCompleted(true);
        const conclusionMsg =
          "Thank you for completing the technical interview! All responses have been captured for candidate scoring.";
        setCurrentQuestion("Interview Completed");
        setTranscript((prev) => [...prev, { role: "interviewer", content: conclusionMsg }]);
        speakText(conclusionMsg);
      }
    } catch (err) {
      console.error("Failed to send message:", err);
      alert("Failed to submit response. Please retry.");
    } finally {
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    if (videoRef.current && stream && isVideoOn) {
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch((err) => console.error("Error playing video:", err));
    }
  }, [stream, isVideoOn]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [stream]);

  return (
    <div className="flex flex-col flex-1 h-screen max-h-screen overflow-hidden max-w-[1600px] mx-auto p-4 md:p-8 gap-6 w-full bg-[#050505] text-white">
      {/* Top Header / Status */}
      <header className="flex items-center justify-between w-full">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full glass-panel flex items-center justify-center overflow-hidden border border-white/10 bg-white/5 p-1.5">
            <img src="/favicon.ico" alt="Conlatus Logo" className="w-full h-full object-contain" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold tracking-wide">{roleTitle}</h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/70 border border-white/10">
                {companyName}
              </span>
            </div>
            <p className="text-xs text-white/50 flex items-center gap-1.5 mt-0.5">
              <User size={12} weight="bold" /> {candidateName}
              {candidateEmail && <span>• {candidateEmail}</span>}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 border border-white/10">
            <Clock size={16} weight="light" className="text-white/70" />
            <span className="text-xs font-mono text-white/90">{formatTimer(elapsedSeconds)}</span>
          </div>

          {isCompleted ? (
            <div className="px-4 py-2 rounded-full bg-violet-500/20 text-violet-300 text-xs font-semibold flex items-center gap-1.5 border border-violet-500/30 shadow-lg shadow-violet-500/10">
              <CheckCircle size={15} weight="fill" /> Session Completed
            </div>
          ) : (
            <SpecularButton
              size="sm"
              radius={999}
              tint="#ef4444"
              tintOpacity={0.15}
              textColor="#fca5a5"
              lineColor="#f87171"
              baseColor="#450a0a"
              intensity={1.2}
              onClick={() => {
                if (confirm("Are you sure you want to conclude this interview?")) {
                  setIsCompleted(true);
                  speakText("The interview has ended.");
                }
              }}
            >
              End Interview
            </SpecularButton>
          )}

          {onExit && (
            <button
              onClick={onExit}
              title="Exit Portal"
              className="p-2.5 rounded-full glass-panel border border-white/10 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            >
              <SignOut size={16} />
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0 pb-24 md:pb-0">
        {/* Main Video Feed */}
        <div className="flex-[2] w-full min-h-0 relative rounded-[2rem] p-2 glass-panel flex flex-col">
          <div className="flex-1 rounded-[calc(2rem-0.5rem)] glass-panel-inner relative overflow-hidden flex items-center justify-center bg-[#050505]">
            {/* Background Fallback */}
            <div className="absolute inset-0 bg-gradient-to-br from-zinc-900 via-[#111] to-[#050505] opacity-80 z-0" />

            {/* User Video Feed */}
            <motion.div
              className="absolute inset-0 z-10"
              initial={{ opacity: 0 }}
              animate={{ opacity: isVideoOn ? 1 : 0 }}
              transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
            >
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover -scale-x-100" />
            </motion.div>

            {/* Camera Off State */}
            {!isVideoOn && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center text-white/30 gap-3">
                <VideoCameraSlash size={36} weight="light" />
                <span className="text-sm font-medium tracking-wide">Camera is off</span>
                <button
                  onClick={() => toggleMedia("video")}
                  className="text-xs text-white/60 hover:text-white underline underline-offset-4"
                >
                  Turn On Camera
                </button>
              </div>
            )}

            {/* Status notification banner (recording / AI evaluating) */}
            {isRecording && (
              <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-red-500/20 backdrop-blur-md border border-red-500/40 text-red-300 text-xs px-4 py-2 rounded-full flex items-center gap-2 animate-pulse shadow-lg shadow-red-500/20">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                Recording Answer... Click mic to submit response
              </div>
            )}

            {isProcessing && (
              <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 bg-blue-500/20 backdrop-blur-md border border-blue-500/40 text-blue-300 text-xs px-4 py-2 rounded-full flex items-center gap-2 shadow-lg shadow-blue-500/20">
                <Spinner size={14} className="animate-spin" />
                AI is analyzing speech and scoring criteria...
              </div>
            )}

            {/* The Dock (Centered relative to video feed) */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
              className="absolute bottom-8 left-1/2 -translate-x-1/2 z-50"
            >
              <SpecularContainer
                radius={999}
                tintOpacity={0}
                className="glass-panel p-2 rounded-full shadow-2xl border border-white/15"
                contentClassName="flex items-center gap-3"
              >
                <DockButton
                  title={isRecording ? "Stop Recording & Submit" : isMicOn ? "Hold/Click to Speak" : "Turn On Mic"}
                  icon={
                    isRecording ? (
                      <Microphone weight="fill" className="text-red-500 animate-pulse text-2xl" />
                    ) : isMicOn ? (
                      <Microphone weight="fill" className="text-violet-400 text-2xl" />
                    ) : (
                      <MicrophoneSlash weight="fill" className="text-2xl text-white/50" />
                    )
                  }
                  active={isMicOn || isRecording}
                  disabled={isCompleted || isProcessing}
                  onClick={() => {
                    if (isCompleted) return;
                    if (!isMicOn) {
                      toggleMedia("audio");
                    } else {
                      if (isRecording) {
                        handlePushToTalkStop();
                      } else {
                        handlePushToTalkStart();
                      }
                    }
                  }}
                />
                <DockButton
                  title={isVideoOn ? "Turn Camera Off" : "Turn Camera On"}
                  icon={
                    isVideoOn ? (
                      <VideoCamera weight="fill" className="text-violet-400 text-2xl" />
                    ) : (
                      <VideoCameraSlash weight="fill" className="text-2xl text-white/50" />
                    )
                  }
                  active={isVideoOn}
                  onClick={() => toggleMedia("video")}
                />
              </SpecularContainer>
            </motion.div>
          </div>
        </div>

        {/* Side Panel Bento Grid */}
        <div className="w-full lg:flex-[1] flex-1 flex flex-col gap-6 min-h-0">
          {/* Transcript Panel */}
          <SpecularContainer
            radius={32}
            tintOpacity={0}
            className="flex-1 min-h-0 rounded-[2rem] p-2 glass-panel"
            contentClassName="w-full h-full"
          >
            <div className="w-full h-full rounded-[calc(2rem-0.5rem)] glass-panel-inner p-6 flex flex-col relative overflow-hidden">
              <div className="flex items-center justify-between mb-4 shrink-0">
                <div className="flex items-center gap-2">
                  <ChatCircleText size={18} weight="light" className="text-white/60" />
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-white/60">
                    Live Transcript
                  </h3>
                </div>
                {isProcessing && (
                  <span className="text-[10px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full animate-pulse border border-blue-500/20">
                    Transcribing...
                  </span>
                )}
              </div>

              {/* Scrollable Transcript List */}
              <div className="flex-1 min-h-0 relative">
                <div className="absolute inset-0 overflow-y-auto pr-2 pb-6 space-y-5">
                  {transcript.map((msg, idx) => (
                    <div key={idx} className="flex gap-3">
                      {msg.role === "interviewer" ? (
                        <div className="w-6 h-6 rounded-full bg-white/10 shrink-0 flex items-center justify-center text-[10px] font-bold mt-1 text-white/90 border border-white/10">
                          AI
                        </div>
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-violet-500/20 shrink-0 flex items-center justify-center text-[10px] font-bold mt-1 text-violet-300 border border-violet-500/30">
                          You
                        </div>
                      )}
                      <div className="flex-1">
                        <p
                          className={`text-sm leading-relaxed ${
                            msg.role === "interviewer" ? "text-white/85" : "text-white/95"
                          }`}
                        >
                          {msg.content}
                        </p>
                      </div>
                    </div>
                  ))}
                  {isProcessing && (
                    <div className="flex gap-3 items-center text-white/40 text-xs italic">
                      <Spinner size={14} className="animate-spin" />
                      Evaluating candidate response against rubric...
                    </div>
                  )}
                  <div ref={transcriptEndRef} />
                </div>
              </div>

              {/* Text Fallback Input */}
              <form onSubmit={handleSendTextMessage} className="mt-3 pt-3 border-t border-white/10 flex gap-2">
                <input
                  type="text"
                  value={typedMessage}
                  onChange={(e) => setTypedMessage(e.target.value)}
                  placeholder={
                    isCompleted
                      ? "Interview completed"
                      : "Type answer or use Push-To-Talk mic..."
                  }
                  disabled={isCompleted || isProcessing}
                  className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-white/40 focus:outline-none focus:border-violet-500/50"
                />
                <button
                  type="submit"
                  disabled={!typedMessage.trim() || isProcessing || isCompleted}
                  className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-violet-500/20 text-white hover:text-violet-300 border border-white/10 text-xs font-medium transition-all disabled:opacity-30 flex items-center justify-center"
                >
                  <PaperPlaneRight size={14} weight="fill" />
                </button>
              </form>
            </div>
          </SpecularContainer>

          {/* Current Question */}
          <SpecularContainer
            radius={32}
            tintOpacity={0}
            className="h-[170px] rounded-[2rem] p-1.5 glass-panel shrink-0"
            contentClassName="w-full h-full"
          >
            <div className="w-full h-full rounded-[calc(2rem-0.375rem)] glass-panel-inner p-6 relative overflow-hidden flex flex-col justify-between gap-4">
              <div className="absolute inset-0 bg-white/[0.02]" />
              <div className="relative z-10 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/40">
                  {isCompleted ? "Status" : "Current Question"}
                </p>
                {isCompleted && (
                  <span className="text-[10px] text-violet-400 font-medium">Session Finalized</span>
                )}
              </div>
              <div className="relative z-10 overflow-y-auto max-h-[85px] pr-1">
                <p className="text-sm md:text-base font-medium text-white/90 leading-relaxed">
                  {isCompleted
                    ? "The interview has ended. Thank you for your time!"
                    : currentQuestion
                    ? `"${currentQuestion}"`
                    : "Waiting for question..."}
                </p>
              </div>
            </div>
          </SpecularContainer>
        </div>
      </main>
    </div>
  );
}

function DockButton({
  icon,
  active = false,
  disabled = false,
  title,
  onClick,
}: {
  icon: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  title?: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`group relative w-14 h-14 rounded-full hover:bg-white/15 border transition-all duration-500 ease-fluid active:scale-[0.92] flex items-center justify-center ${
        disabled ? "opacity-40 cursor-not-allowed" : ""
      } ${active ? "bg-white/15 border-white/25 shadow-lg" : "bg-white/5 border-transparent"}`}
    >
      <div
        className={`transition-colors duration-500 ${
          active ? "text-white" : "text-white/60 group-hover:text-white"
        }`}
      >
        {icon}
      </div>
    </button>
  );
}
