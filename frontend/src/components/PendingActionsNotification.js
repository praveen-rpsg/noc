import React, { useState, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { ScrollArea } from './ui/scroll-area';
import { Textarea } from './ui/textarea';
import { agentExecApi } from '../services/api';
import { toast } from 'sonner';
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCcw,
  Power,
  Link,
  Settings,
  HardDrive,
  Zap,
  Loader2,
  Clock
} from 'lucide-react';
import { format } from 'date-fns';

const actionIcons = {
  device_reboot: Power,
  link_reset: Link,
  firmware_update: Settings,
  factory_reset: RefreshCcw,
  power_cycle: Zap,
  hardware_replacement: HardDrive,
};

const riskColors = {
  low: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  high: 'bg-orange-50 text-orange-700 border-orange-200',
  critical: 'bg-red-50 text-red-700 border-red-200',
};

export default function PendingActionsNotification() {
  const [pendingActions, setPendingActions] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const fetchPendingActions = useCallback(async () => {
    try {
      const [actionsRes, countRes] = await Promise.all([
        agentExecApi.getPendingActions(),
        agentExecApi.getPendingCount()
      ]);
      setPendingActions(actionsRes.data);
      setPendingCount(countRes.data.count);
    } catch (error) {
      console.error('Failed to fetch pending actions:', error);
    }
  }, []);

  useEffect(() => {
    fetchPendingActions();
    // Poll every 10 seconds
    const interval = setInterval(fetchPendingActions, 60000);
    return () => clearInterval(interval);
  }, [fetchPendingActions]);

  const handleApprove = async () => {
    if (!selectedAction) return;
    setProcessing(true);
    try {
      await agentExecApi.approveAction(selectedAction.id);
      toast.success('Action approved and executed');
      setConfirmDialogOpen(false);
      setSelectedAction(null);
      fetchPendingActions();
    } catch (error) {
      toast.error('Failed to approve action');
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!selectedAction) return;
    setProcessing(true);
    try {
      await agentExecApi.rejectAction(selectedAction.id, rejectReason);
      toast.success('Action rejected');
      setRejectDialogOpen(false);
      setSelectedAction(null);
      setRejectReason('');
      fetchPendingActions();
    } catch (error) {
      toast.error('Failed to reject action');
    } finally {
      setProcessing(false);
    }
  };

  const openConfirmDialog = (action) => {
    setSelectedAction(action);
    setConfirmDialogOpen(true);
  };

  const openRejectDialog = (action) => {
    setSelectedAction(action);
    setRejectDialogOpen(true);
  };

  const ActionIcon = ({ actionType }) => {
    const Icon = actionIcons[actionType] || AlertTriangle;
    return <Icon className="h-5 w-5" />;
  };

  return (
    <>
      {/* Bell Icon with Badge */}
      <div className="relative">
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          onClick={() => setIsOpen(!isOpen)}
          data-testid="pending-actions-bell"
        >
          <Bell className="h-5 w-5" />
          {pendingCount > 0 && (
            <Badge 
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 bg-red-500 text-white text-xs"
              data-testid="pending-actions-count"
            >
              {pendingCount > 9 ? '9+' : pendingCount}
            </Badge>
          )}
        </Button>

        {/* Dropdown Panel */}
        {isOpen && (
          <Card className="absolute right-0 top-12 w-96 z-50 shadow-lg" data-testid="pending-actions-panel">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  Actions Requiring Confirmation
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={fetchPendingActions}>
                  <RefreshCcw className="h-3 w-3" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <ScrollArea className="h-80">
                {pendingActions.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    <p>No pending actions</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {pendingActions.map((action) => (
                      <div
                        key={action.id}
                        className="p-3 rounded-lg border bg-white hover:bg-slate-50 transition-colors"
                        data-testid={`pending-action-${action.id}`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`p-2 rounded-lg ${riskColors[action.risk_level] || riskColors.high}`}>
                            <ActionIcon actionType={action.action_type} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm capitalize">
                              {action.action_type?.replace(/_/g, ' ')}
                            </p>
                            <p className="text-xs text-muted-foreground truncate">
                              {action.device_name || 'Unknown Device'}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {action.action_description}
                            </p>
                            <div className="flex items-center gap-2 mt-2">
                              <Badge variant="outline" className={riskColors[action.risk_level]}>
                                {action.risk_level} risk
                              </Badge>
                              {action.estimated_downtime && (
                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {action.estimated_downtime}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2 mt-3">
                          <Button
                            size="sm"
                            className="flex-1 bg-green-600 hover:bg-green-700"
                            onClick={() => openConfirmDialog(action)}
                            data-testid={`approve-action-${action.id}`}
                          >
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => openRejectDialog(action)}
                            data-testid={`reject-action-${action.id}`}
                          >
                            <XCircle className="h-3 w-3 mr-1" />
                            Reject
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Confirm Approval Dialog */}
      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Confirm Action Execution
            </DialogTitle>
          </DialogHeader>
          
          {selectedAction && (
            <div className="space-y-4">
              <Card className={`${riskColors[selectedAction.risk_level]} border-2`}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-white/50 rounded-lg">
                      <ActionIcon actionType={selectedAction.action_type} />
                    </div>
                    <div>
                      <p className="font-semibold capitalize">
                        {selectedAction.action_type?.replace(/_/g, ' ')}
                      </p>
                      <p className="text-sm">
                        Device: {selectedAction.device_name || 'Unknown'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <div className="text-sm space-y-2">
                <p><strong>Description:</strong> {selectedAction.action_description}</p>
                {selectedAction.command_to_execute && (
                  <div>
                    <p className="font-medium">Command to execute:</p>
                    <code className="block p-2 bg-slate-100 rounded text-xs font-mono">
                      {selectedAction.command_to_execute}
                    </code>
                  </div>
                )}
                <p><strong>Risk Level:</strong> <span className="capitalize">{selectedAction.risk_level}</span></p>
                {selectedAction.estimated_downtime && (
                  <p><strong>Estimated Downtime:</strong> {selectedAction.estimated_downtime}</p>
                )}
              </div>
              
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <strong>⚠️ Warning:</strong> This action will be executed immediately upon approval. 
                  Ensure you have verified the action is safe to proceed.
                </p>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialogOpen(false)} disabled={processing}>
              Cancel
            </Button>
            <Button 
              className="bg-green-600 hover:bg-green-700"
              onClick={handleApprove}
              disabled={processing}
              data-testid="confirm-approve-btn"
            >
              {processing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Executing...
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Approve & Execute
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-500" />
              Reject Action
            </DialogTitle>
          </DialogHeader>
          
          {selectedAction && (
            <div className="space-y-4">
              <p className="text-sm">
                You are about to reject the <strong className="capitalize">{selectedAction.action_type?.replace(/_/g, ' ')}</strong> action 
                for device <strong>{selectedAction.device_name || 'Unknown'}</strong>.
              </p>
              
              <div>
                <label className="text-sm font-medium">Reason for rejection (optional):</label>
                <Textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Enter reason for rejecting this action..."
                  className="mt-2"
                  rows={3}
                />
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialogOpen(false)} disabled={processing}>
              Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={handleReject}
              disabled={processing}
              data-testid="confirm-reject-btn"
            >
              {processing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4 mr-2" />
                  Reject Action
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Click outside to close */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
