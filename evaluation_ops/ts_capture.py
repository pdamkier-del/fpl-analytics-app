"""Fail-closed private capture at the existing original TS completion boundary."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,json,os,stat,subprocess
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fpl_private_ts_ledger',ROOT/'analysis/followup-41-20261122/code/private_ts_ledger.py');ledger=importlib.util.module_from_spec(spec);spec.loader.exec_module(ledger)
class Rejected(Exception):
 def __init__(self,code,message):self.code=code;self.message=message

def reject(code,message):raise Rejected(code,message)
def storage(env=None):
 env=os.environ if env is None else env
 if env.get('GITHUB_ACTIONS')=='true' or env.get('CI')in ['true','1']:reject('public_ci_forbidden','Privat TS-capture er deaktiveret i CI; ingen managerdata må blive til artifacts.')
 value=env.get('FPL_TS_PRIVATE_ROOT');volume_value=env.get('FPL_TS_PRIVATE_VOLUME')
 if not value or not volume_value:reject('private_storage_unconfigured','Privat TS-lagring er ikke konfigureret; beregningen gemmes ikke til evaluering.')
 root=Path(value);volume=Path(volume_value)
 if not root.is_absolute()or not volume.is_absolute()or root.is_symlink()or volume.is_symlink():reject('private_path_invalid','Lagringen kræver absolutte stier uden symlink-omdirigering.')
 root=root.resolve();volume=volume.resolve()
 if volume in [Path('/'),Path('/tmp'),Path('/workspace')]or not os.path.ismount(volume)or not root.is_relative_to(volume)or root==volume:reject('persistent_volume_unverified','En særskilt vedvarende privat mount er ikke verificeret; midlertidig disk accepteres ikke.')
 if not root.is_dir():reject('private_directory_missing','Den private mappe skal provisioneres på den verificerede volume før capture.')
 st=root.stat()
 if st.st_uid!=os.geteuid()or stat.S_IMODE(st.st_mode)!=0o700:reject('private_permissions_invalid','Den private mappe skal ejes af tjenestebrugeren og have adgang 0700.')
 probe=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True)
 if probe.returncode==0:reject('git_destination_forbidden','Privat TS-lagring må ikke ligge i et Git-worktree.')
 att=root/'storage-attestation.json'
 if not att.is_file()or att.is_symlink():reject('storage_attestation_missing','Driftskvittering for vedvarende, privat lagring og private backups mangler.')
 if att.stat().st_uid!=os.geteuid()or stat.S_IMODE(att.stat().st_mode)!=0o600:reject('storage_attestation_permissions','Lagringskvitteringen skal have samme ejer og adgang 0600.')
 try:a=json.loads(att.read_text())
 except Exception:reject('storage_attestation_invalid','Lagringskvitteringen kan ikke verificeres.')
 if a.get('mount_path')!=str(volume)or a.get('persistent')is not True or a.get('private')is not True or a.get('public_export')is not False or a.get('backups_private')is not True or not a.get('operator_reference'):reject('storage_attestation_invalid','Driftskvitteringen bekræfter ikke privat vedvarende lagring uden offentlig eksport.')
 if not os.access(root,os.W_OK|os.X_OK):reject('private_storage_unwritable','Den private volume er ikke skrivbar for tjenesten.')
 return root

def after_success(forecast,state,result,*,env=None,now=None):
 """Must not mutate inputs or influence model decisions. Missing intention remains unknown."""
 try:
  if result.get('ts_ran')is not True:reject('original_calculation_incomplete','Den originale TS-beregning er ikke gennemført.')
  if result.get('validation_only')is True or state.get('validation_only')is True:reject('validation_fixture_not_observation','En valideringstrup må ikke tælle som en reel managerobservation.')
  root=storage(env);now=now or datetime.now(timezone.utc)
  if now>=ledger.clock(forecast.get('origin_deadline')):reject('deadline_passed','TS-resultatet blev færdigt efter deadline; det arkiveres ikke som en før-deadline-prognose.')
  try:r=ledger.capture(root,forecast,state,result,None,now=now)
  except (OSError,PermissionError):reject('private_write_failed','Den private optagelse kunne ikke skrives varigt; ingen gyldig capture er registreret.')
  except Exception:reject('capture_contract_rejected','Forecast, managerstate, horisont eller keep-squad-kontrol bestod ikke capture-kontrakten.')
  return {'status':'recorded_private','capture_id':r['capture_id'],'intention':'not_supplied','execution':'not_observed','clock_proof':'local_system_clock_only'}
 except Rejected as e:return {'status':'not_captured','reason_code':e.code,'message':e.message}
 except Exception:return {'status':'not_captured','reason_code':'private_storage_check_failed','message':'Den private lagring kunne ikke sikkerhedsverificeres; capture er afvist.'}
