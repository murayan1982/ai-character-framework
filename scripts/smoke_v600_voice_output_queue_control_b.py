"""FW-RT6-6c Control B pending-to-active synthesis handoff gate."""
from __future__ import annotations
import argparse
import inspect
import subprocess
import sys
import threading
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))
EXPECTED_HEAD="820056ff897e7bfdcfa20c3f7d4b14df0633c3b1"
EXPECTED_SURFACE={
"docs/app_integration_contract.md","docs/public_facade.md","docs/v600_realtime_voice_output_contract.md",
"framework/realtime_voice_output.py","framework/realtime_voice_output_queue.py",
"scripts/smoke_v600_voice_output_queue_control_a.py","scripts/smoke_v600_voice_output_queue_control_b.py"}
VOICE_EXPORTS=("SynthesisWorkId","VoiceSynthesisResultEnvelope","VoiceSynthesisActiveGeneration","VoiceSynthesisCancelOutcome","VoiceSynthesisCancelResult","VoiceSynthesisProviderAdapter","VoiceSynthesisStage")
QUEUE_EXPORTS=("VoiceSynthesisPendingWork","VoiceSynthesisEnqueueOutcome","VoiceSynthesisEnqueueResult","VoiceSynthesisPendingClearOutcome","VoiceSynthesisPendingClearResult","VoiceSynthesisQueueEventType","VoiceSynthesisQueueEvent","VoiceSynthesisPendingQueue")
def _assert(c,m):
    if not c: raise AssertionError(m)
def _run(cmd):
    r=subprocess.run(cmd,cwd=PROJECT_ROOT,text=True,capture_output=True,check=False)
    _assert(r.returncode==0,"command failed: "+" ".join(cmd)+"\n"+r.stdout+r.stderr); return r.stdout
def _git(*a): return _run(["git",*a]).strip()
def _changed():
    return {p.strip().replace("\\","/") for p in (_git("diff","--name-only","HEAD").splitlines()+_git("ls-files","--others","--exclude-standard").splitlines()) if p.strip()}
def check_git_surface():
    _assert(_git("rev-parse","HEAD")==EXPECTED_HEAD,"baseline HEAD drift")
    _assert(_git("rev-parse","origin/main")==EXPECTED_HEAD,"baseline origin/main drift")
    _assert(_changed()==EXPECTED_SURFACE,f"Control B exact surface drift: {sorted(_changed())!r}")
    print("[OK] baseline and exact seven-file FW-RT6-6c Control B surface conform")
def _context():
    from framework.identity import SessionId,TurnId,GenerationId
    from framework.realtime_stage import RealtimeStageContext
    return RealtimeStageContext(session_id=SessionId.new(),turn_id=TurnId.new(),generation_id=GenerationId.new())
def _capability():
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability,RuntimeCapabilityState
    return RealtimeVoiceOutputCapability(runtime=RuntimeCapabilityState(configured=True,runtime_available=True,fake_runtime=True,unavailable_reason=None,public_metadata={"adapter":"fake"}),audio_formats=("mp3",))
def check_stable_surfaces():
    import framework,framework.realtime_voice_output as v,framework.realtime_voice_output_queue as q
    _assert(len(framework.__all__)==127,"root-public drift")
    _assert(tuple(v.__all__)==VOICE_EXPORTS,"voice stable exports drift")
    _assert(tuple(q.__all__)==QUEUE_EXPORTS,"queue stable exports drift")
    _assert("ProviderNeutralVoiceSynthesisStage" not in v.__all__,"concrete stage became stable")
    _assert("BoundedVoiceSynthesisPendingQueue" not in q.__all__,"concrete queue became stable")
    sig=inspect.signature(v.VoiceSynthesisStage.start)
    _assert(tuple(sig.parameters)==("self","context","request"),"stable stage start signature drift")
    _assert("work_id" not in sig.parameters,"stable stage protocol gained handoff work_id")
    _assert("handoff_next" not in q.VoiceSynthesisPendingQueue.__dict__,"stable pending protocol gained execution")
    print("[OK] accepted root/voice/queue stable surfaces remain unchanged")
def check_same_work_id_handoff():
    from framework.audio.voice_output import VoiceOutputRequest,VoiceOutputResult
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage,VoiceSynthesisCancelOutcome
    from framework.realtime_voice_output_queue import BoundedVoiceSynthesisPendingQueue,VoiceSynthesisPendingClearOutcome
    entered=threading.Event(); release=threading.Event(); seen=[]
    class Adapter:
        def capability(self): return _capability()
        def synthesize(self,request):
            seen.append(request); entered.set(); _assert(release.wait(5),"provider release timeout")
            return VoiceOutputResult(request_state="generated",audio_ready=True,audio_url="https://example.invalid/control-b")
    q=BoundedVoiceSynthesisPendingQueue(max_pending_depth=2); stage=ProviderNeutralVoiceSynthesisStage(Adapter())
    c1,c2=_context(),_context(); r1=q.enqueue(context=c1,request=VoiceOutputRequest(text="private first")); r2=q.enqueue(context=c2,request=VoiceOutputRequest(text="private second"))
    out=[]; err=[]
    def run():
        try: out.append(q.handoff_next(stage=stage))
        except BaseException as e: err.append(e)
    th=threading.Thread(target=run); th.start(); _assert(entered.wait(5),"handoff did not enter provider")
    active=stage.active_generation; _assert(active is not None,"handoff did not become active")
    _assert(active.context==c1 and active.work_id==r1.work.work_id,"enqueue-to-active identity drift")
    _assert(q.pending_work==(r2.work,),"active work remained pending or FIFO drifted")
    cleared=q.clear_pending(context=c1)
    _assert(cleared.outcome is VoiceSynthesisPendingClearOutcome.NOTHING_CLEARED,"active work was still clearable as pending")
    _assert(stage.active_generation==active,"pending clear changed active generation")
    unsupported=stage.cancel(context=c1,work_id=active.work_id)
    _assert(unsupported.outcome is VoiceSynthesisCancelOutcome.UNSUPPORTED,"Control B overclaimed active cancel")
    release.set(); th.join(5); _assert(not th.is_alive(),"handoff worker stuck"); _assert(not err,f"handoff failed: {err!r}")
    _assert(len(out)==1 and out[0].work_id==r1.work.work_id and out[0].context==c1,"active-to-result identity drift")
    _assert(stage.active_generation is None,"active state did not clear")
    _assert(len(seen)==1 and isinstance(seen[0],VoiceOutputRequest),"adapter boundary drift")
    print("[OK] pending-to-active handoff preserves exact enqueue-time work ID and state ownership")
def check_claim_rejection_preserves_pending():
    from framework.audio.voice_output import VoiceOutputRequest,VoiceOutputResult
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage
    from framework.realtime_voice_output_queue import BoundedVoiceSynthesisPendingQueue
    entered=threading.Event(); release=threading.Event()
    class Blocking:
        def capability(self): return _capability()
        def synthesize(self,request): entered.set(); _assert(release.wait(5),"busy release timeout"); return VoiceOutputResult(request_state="unavailable")
    stage=ProviderNeutralVoiceSynthesisStage(Blocking()); busy_context=_context(); worker=threading.Thread(target=lambda: stage.start(context=busy_context,request=VoiceOutputRequest(text="busy"))); worker.start(); _assert(entered.wait(5),"stage not busy")
    q=BoundedVoiceSynthesisPendingQueue(max_pending_depth=1); enq=q.enqueue(context=_context(),request=VoiceOutputRequest(text="queued"))
    try: q.handoff_next(stage=stage)
    except RuntimeError as e: _assert("already active" in str(e).lower(),"busy claim error drift")
    else: raise AssertionError("busy stage accepted pending handoff")
    _assert(q.pending_work==(enq.work,),"busy stage mutated pending FIFO")
    release.set(); worker.join(5); _assert(not worker.is_alive(),"busy worker stuck")
    closed=ProviderNeutralVoiceSynthesisStage(Blocking()); closed.close(); q2=BoundedVoiceSynthesisPendingQueue(max_pending_depth=1); enq2=q2.enqueue(context=_context(),request=VoiceOutputRequest(text="closed queued"))
    try: q2.handoff_next(stage=closed)
    except RuntimeError as e: _assert("closed" in str(e).lower(),"closed claim error drift")
    else: raise AssertionError("closed stage accepted pending handoff")
    _assert(q2.pending_work==(enq2.work,),"closed stage mutated pending FIFO")
    print("[OK] closed/busy stage claim rejection preserves pending FIFO without restore race")
def check_execution_failure_is_not_requeued():
    from framework.audio.voice_output import VoiceOutputRequest
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage
    from framework.realtime_voice_output_queue import BoundedVoiceSynthesisPendingQueue
    class Failing:
        def capability(self): return _capability()
        def synthesize(self,request): raise RuntimeError("private provider failure")
    stage=ProviderNeutralVoiceSynthesisStage(Failing()); q=BoundedVoiceSynthesisPendingQueue(max_pending_depth=2); r=q.enqueue(context=_context(),request=VoiceOutputRequest(text="fail once"))
    try: q.handoff_next(stage=stage)
    except RuntimeError as e: _assert("private provider failure" in str(e),"provider failure propagation drift")
    else: raise AssertionError("provider failure was swallowed")
    _assert(q.pending_count==0,"active execution failure was incorrectly requeued")
    _assert(stage.active_generation is None,"active state leaked after provider failure")
    _assert(r.work not in q.pending_work,"failed active work remained pending")
    print("[OK] post-claim provider failure clears active state and is not silently requeued")
def check_regressions():
    _run([sys.executable,"scripts/smoke_v600_voice_output_queue_control_a.py","--source-only"])
    _run([sys.executable,"scripts/smoke_v600_realtime_voice_output_control_b.py","--source-only"])
    print("[OK] accepted FW-RT6-6c Control A and FW-RT6-6a active-stage regressions conform")
def check_docs():
    contract=(PROJECT_ROOT/"docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    task=(PROJECT_ROOT/"docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in ("FW-RT6-6c-B-PENDING-ACTIVE-HANDOFF:BEGIN",EXPECTED_HEAD,"exact change surface:\n7 files","same enqueue/active/result work ID:\nTrue","Control C:\nNOT_AUTHORIZED","FW-RT6-6d","FW-RT6-6e","127 / UNCHANGED"):
        _assert(marker in contract,f"Control B contract marker missing: {marker}")
    s=task.index("## FW-RT6-6c — Bounded voice-output work queue"); e=task.index("\n---\n",s); sec=task[s:e]
    _assert(sec.count("- [ ]")==7 and sec.count("- [x]")==0,"Control B must not close aggregate tasklist")
    print("[OK] Control B docs and deferred 6d/6e boundaries conform")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source-only",action="store_true"); a=ap.parse_args()
    if not a.source_only: check_git_surface()
    check_stable_surfaces(); check_same_work_id_handoff(); check_claim_rejection_preserves_pending(); check_execution_failure_is_not_requeued(); check_regressions(); check_docs()
    print("v600_rt6_6c_control_b_status: implemented-awaiting-review")
    print("v600_rt6_6c_control_b_exact_surface: 7 files")
    print("v600_rt6_6c_same_work_id_handoff: True / PASS")
    print("v600_rt6_6c_pending_active_separate: True / PASS")
    print("v600_rt6_6c_claim_rejection_preserves_pending: True / PASS")
    print("v600_rt6_6c_pending_clear_changes_active: False / PASS")
    print("v600_rt6_6c_generation_cancel_changed: False")
    print("v600_rt6_6c_artifact_invalidation_changed: False")
    print("v600_rt6_6c_host_playback_changed: False")
    print("v600_rt6_6c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6c_tasklist_closed: 0 / 7")
    print("v600_rt6_6c_control_c: NOT_AUTHORIZED")
    print("v600_rt6_6c_commit_push: NOT_AUTHORIZED")
if __name__=="__main__": main()
