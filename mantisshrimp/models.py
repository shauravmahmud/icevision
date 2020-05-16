# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/08_models.ipynb (unless otherwise specified).

__all__ = ['RCNN', 'MantisMaskRCNN', 'MantisFasterRCNN', 'show_pred', 'show_preds']

# Cell
from .imports import *
from .core import *
from .data.all import *

# Cell
class RCNN(LightningModule):
    def __init__(self, metrics=None):
        super().__init__()
        self.metrics = metrics or []
        for metric in self.metrics: metric.register_model(self)

    def training_step(self, b, b_idx):
        xb,yb = b
        losses = self(xb,list(yb))
        loss = sum(losses.values())
        log = {'train/loss': loss, **{f'train/{k}':v for k,v in losses.items()}}
        return {'loss': loss, 'log': log}

    def validation_step(self, b, b_idx):
        xb,yb = b
        with torch.no_grad(): losses,preds = self(xb,list(yb))
        loss = sum(losses.values())
        losses = {f'valid/{k}':v for k,v in losses.items()}
        res = {}
        for metric in self.metrics:
            o = metric.step(xb, yb, preds)
            if notnone(o): raise NotImplementedError # How to update res?
        res.update({'valid/loss': loss, **losses})
        return res

    def validation_epoch_end(self, outs):
        res = {}
        for metric in self.metrics:
            o = metric.end(outs)
            if notnone(o): raise NotImplementedError # How to update res?
        log = {k:torch.stack(v).mean() for k,v in mergeds(outs).items()}
        res.update({'val_loss': log['valid/loss'], 'log': log})
        return res

    def configure_optimizers(self):
        params = [p for p in self.parameters() if p.requires_grad]
        opt = torch.optim.Adam(params)
        return [opt]

# Cell
class MantisMaskRCNN(RCNN):
    @delegates(MaskRCNN.__init__)
    def __init__(self, n_class, h=256, pretrained=True, metrics=None, **kwargs):
        super().__init__(metrics=metrics)
        self.m = maskrcnn_resnet50_fpn(pretrained=pretrained, **kwargs)
        in_features = self.m.roi_heads.box_predictor.cls_score.in_features
        self.m.roi_heads.box_predictor = FastRCNNPredictor(in_features, n_class)
        in_features_mask = self.m.roi_heads.mask_predictor.conv5_mask.in_channels
        self.m.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, h, n_class)
    def forward(self, images, targets=None): return self.m(images, targets)

# Cell
class MantisFasterRCNN(RCNN):
    @delegates(FasterRCNN.__init__)
    def __init__(self, n_class, h=256, pretrained=True, metrics=None, **kwargs):
        super().__init__(metrics=metrics)
        self.m = fasterrcnn_resnet50_fpn(pretrained=pretrained, **kwargs)
        in_features = self.m.roi_heads.box_predictor.cls_score.in_features
        self.m.roi_heads.box_predictor = FastRCNNPredictor(in_features, n_class)
    def forward(self, images, targets=None): return self.m(images, targets)

# Cell
@patch
def predict(self:RCNN, ims=None, rs=None):
    if bool(ims)==bool(rs): raise ValueError('You should either pass ims or rs')
    if notnone(rs): ims = [open_img(o.iinfo.fp) for o in rs]
    xs = [im2tensor(o).to(model_device(self)) for o in ims]
    self.eval()
    return ims, self(xs)

# Cell
def show_pred(im, pred, mask_thresh=.5, ax=None):
    # TODO: Implement mask and keypoint
    bboxes,masks,kpts = None,None,None
    if 'boxes' in pred: bboxes = [BBox.from_xyxy(*o) for o in pred['boxes']]
    if 'masks' in pred: masks = Mask(to_np((pred['masks']>.5).long()[:,0,:,:]))
    return show_annot(im, bboxes=bboxes, masks=masks, ax=ax)

# Cell
def show_preds(ims, preds, mask_thresh=.5):
    return grid2([partial(show_pred,im=im,pred=pred,mask_thresh=mask_thresh)
                  for im,pred in zip(ims,preds)])