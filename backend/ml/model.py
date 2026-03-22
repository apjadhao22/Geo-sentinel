import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class Encoder(nn.Module):
    def __init__(self, in_channels=3):
        super().__init__()
        self.enc1 = ConvBlock(in_channels, 64)
        self.enc2 = ConvBlock(64, 128)
        self.enc3 = ConvBlock(128, 256)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        return e1, e2, e3


class SiameseUNet(nn.Module):
    def __init__(self, in_channels: int = 3):
        super().__init__()
        self.encoder = Encoder(in_channels)
        # Decoder channel math:
        # bottleneck: 256+256=512 -> up2 -> 128
        # up2 out (128) + e2_a (128) + e2_b (128) = 384 -> dec2
        # up1 out (64) + e1_a (64) + e1_b (64) = 192 -> dec1
        self.up2 = nn.ConvTranspose2d(512, 128, 2, stride=2)
        self.dec2 = ConvBlock(384, 128)
        self.up1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec1 = ConvBlock(192, 64)
        self.out_conv = nn.Conv2d(64, 1, 1)

    def forward(self, x_before: torch.Tensor, x_after: torch.Tensor) -> torch.Tensor:
        e1_a, e2_a, e3_a = self.encoder(x_before)
        e1_b, e2_b, e3_b = self.encoder(x_after)

        x = torch.cat([e3_a, e3_b], dim=1)    # 512
        x = self.up2(x)                         # 128
        x = torch.cat([x, e2_a, e2_b], dim=1)  # 384
        x = self.dec2(x)                        # 128
        x = self.up1(x)                         # 64
        x = torch.cat([x, e1_a, e1_b], dim=1)  # 192
        x = self.dec1(x)                        # 64
        return torch.sigmoid(self.out_conv(x))  # (B, 1, H, W) in [0,1]
