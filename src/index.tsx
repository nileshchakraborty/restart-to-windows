import { useEffect, useState } from "react";
import { FaWindows } from "react-icons/fa";

import { callable, definePlugin, toaster } from "@decky/api";
import {
  ButtonItem,
  ConfirmModal,
  Field,
  PanelSection,
  PanelSectionRow,
  showModal,
  staticClasses,
  SteamSpinner,
} from "@decky/ui";

type RestartSupport = {
  available: boolean;
  error?: string;
};

type RestartResult = {
  ok: boolean;
  error?: string;
};

const getRestartSupport = callable<[], RestartSupport>("get_restart_support");
const prepareRestartToWindows = callable<[], RestartResult>(
  "prepare_restart_to_windows",
);

function Content() {
  const [support, setSupport] = useState<RestartSupport | null>(null);
  const [isRestarting, setIsRestarting] = useState(false);

  useEffect(() => {
    let mounted = true;

    getRestartSupport()
      .then((result) => {
        if (mounted) setSupport(result);
      })
      .catch((error) => {
        if (mounted) {
          setSupport({
            available: false,
            error: error instanceof Error ? error.message : "Support check failed.",
          });
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const restart = async () => {
    setIsRestarting(true);

    try {
      const result = await prepareRestartToWindows();
      if (!result.ok) {
        toaster.toast({
          title: "Could not restart to Windows",
          body: result.error ?? "An unknown error occurred.",
          critical: true,
          duration: 8000,
        });
        return;
      }

      if (typeof SteamClient?.System?.RestartPC !== "function") {
        toaster.toast({
          title: "Windows is ready for the next boot",
          body: "Steam could not restart the device. Use Power → Restart to continue.",
          critical: true,
          duration: 10000,
        });
        return;
      }

      SteamClient.System.RestartPC();
    } catch (error) {
      toaster.toast({
        title: "Could not restart to Windows",
        body: error instanceof Error ? error.message : "An unknown error occurred.",
        critical: true,
        duration: 8000,
      });
    } finally {
      setIsRestarting(false);
    }
  };

  const confirmRestart = () => {
    showModal(
      <ConfirmModal
        strTitle="Restart to Windows?"
        strDescription="This uses Windows for the next boot only. Your normal boot order will not be changed."
        strOKButtonText="Restart"
        strCancelButtonText="Cancel"
        bDestructiveWarning
        onOK={() => void restart()}
      />,
    );
  };

  if (support === null) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <SteamSpinner />
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (!support.available) {
    return (
      <PanelSection title="Unavailable">
        <PanelSectionRow>
          <Field>{support.error ?? "Restart to Windows is not configured."}</Field>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <PanelSection>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          label="Restart to Windows"
          description="Use Windows for the next boot, then return to the normal boot order."
          disabled={isRestarting}
          onClick={confirmRestart}
        >
          {isRestarting ? "Restarting..." : "Restart"}
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}

export default definePlugin(() => ({
  name: "Restart to Windows",
  titleView: <div className={staticClasses.Title}>Restart to Windows</div>,
  content: <Content />,
  icon: <FaWindows />,
}));
