import os
import uuid
from datetime import datetime

from django.db import models
from PIL import Image as PILImage
from PIL import ImageOps
from shortuuid.django_fields import ShortUUIDField


def set_preview(obj, filename):
    """
    Used as `poster` image for `<model-viewer>`.
    NOTE: Preview will not being resized / compressed since it should be either manually / auto-staged.
    FIXME: LATE_EXP: Auto-stage the Preview when a reconstruction is available.

    """
    upload_to = f"models/{obj.ID}"
    filename = f"{obj.ID}_prev.png"

    return os.path.join(upload_to, filename)


def set_thumbnail(obj, filename):
    """
    Used for the list in the nav.

    """
    upload_to = f"models/{obj.ID}"
    filename = f"{obj.ID}_thumb.png"

    return os.path.join(upload_to, filename)


class Mesh(models.Model):
    # Short for ease of use
    ID = ShortUUIDField(
        primary_key=True, length=16, max_length=16, verbose_name="Mesh ID"
    )

    # Metadata
    name = models.CharField(max_length=200, blank=False)
    description = models.TextField(
        blank=True, verbose_name="Description", default="Placeholder Text"
    )

    country = models.CharField(max_length=200, blank=False, default="India")
    state = models.CharField(max_length=200, blank=False, default="Odisha")
    district = models.CharField(max_length=200, blank=False, default="Khordha")

    preview = models.ImageField(
        upload_to=set_preview, blank=False, verbose_name="Mesh Preview"
    )
    thumbnail = models.ImageField(
        upload_to=set_thumbnail, blank=False, verbose_name="Mesh Thumbnail"
    )

    # Auto-generated - Used for most tasks
    verbose_id = models.CharField(
        max_length=200,
        blank=True,
        unique=True,
        editable=False,
        default="<auto-generated using country, state & district>",
        verbose_name="Verbose ID",
    )
    # Multiple choices for status: [Pending, Processing, Live, Error]
    status_options = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Live", "Live"),
        ("Error", "Error"),
    ]
    status = models.CharField(
        max_length=50, blank=False, choices=status_options, default="Pending"
    )

    # Whether the mesh is accepting images any more
    completed = models.BooleanField(default=False, verbose_name="Completed")
    # Whether to hide the model from the frontend
    hidden = models.BooleanField(default=False, verbose_name="Hidden")

    # NOTE: Directory structure: [S_DIR] = STATIC_ROOT / models | [M_DIR] = MEDIA_ROOT / models | [ID] = Mesh ID
    # [M_DIR]/[ID]/images/ <- Images are uploaded here by default
    # [M_DIR]/[ID]_thumb.[image ext] file - Thumbnail <- Shown in list
    # [M_DIR]/[ID]_prev.[image ext] file - Preview <- Shown in viewer
    # [S_DIR]/[ID]/cache/[RUN_ID]/ <- MeshOps cache
    # [S_DIR]/[ID]/[ID]_deci.glb <- Decimated mesh
    # FIXME: NOTE: obj2gltf bug for converting meshes above ~2.1 GB to .glb.
    # Other option is .gltf, but then no single texture-maps.

    ## Reconstruction settings
    # NOTE: center_image is admin-only.
    # If need be, an admin can set the filename (no ext)
    # of an image in the .../images/ folder.
    # This feeds into sfmTransform(center_image) to orient the mesh with.
    center_image = models.CharField(
        max_length=200, blank=True, verbose_name="Center Image"
    )
    # Rotation and minimum observation angle for `sfmRotate`, `meshing` & <model-viewer>
    rotaX = models.IntegerField(default=0, verbose_name="Rotation about X-axis")
    rotaY = models.IntegerField(default=0, verbose_name="Rotation about Y-axis")
    rotaZ = models.IntegerField(default=0, verbose_name="Rotation about Z-axis")
    # NOTE: Controls whether to use sfmRotate or orient using <model-viewer>
    # Ideally, we do not want to sfmRotate for each new run.
    # NOTE: Use orientMesh to trigger sfmRotate (if needed or if center_image is
    # not working well), when model is "complete", then reset rota* to 0.
    orientMesh = models.BooleanField(default=False, verbose_name="Orient Mesh")
    minObsAng = models.IntegerField(
        default=30, verbose_name="Minimum Observation Angle"
    )
    denoise = models.BooleanField(default=False, verbose_name="Denoise")

    # Set automatically
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)
    reconstructed_at = models.DateTimeField(
        "Last reconstructed at", blank=True, null=True
    )

    class Meta:
        ordering = ["-updated_at"]
        verbose_name_plural = "Meshes"

    def __str__(self):
        return self.verbose_id

    def __repr__(self):
        return f"""
                Mesh(
                    {self.ID},
                    {self.name},
                    {self.description},
                    {self.created_at},
                    {self.updated_at},
                    {self.reconstructed_at},
                    {self.status},
                    {self.completed},
                    {self.hidden}
                )
                """

    def save(self, *args, **kwargs):
        self.verbose_id = (
            self.country + "__" + self.state + "__" + self.district + "__" + self.name
        ).replace(" ", "_")
        super().save(*args, **kwargs)

        # Resizes & compresses preview image
        if self.thumbnail:
            # Load the uploaded image
            image = PILImage.open(self.thumbnail.path)
            image = ImageOps.exif_transpose(image)
            aspect_ratio = image.width / image.height
            new_width = image.width
            new_height = image.height
            min_dimension = 400

            if image.width >= min_dimension and image.height >= min_dimension:
                # Preserve aspect ratio
                if aspect_ratio > 1:  # Landscape
                    new_width = max(min_dimension, int(min_dimension * aspect_ratio))
                    new_height = min_dimension
                else:  # Portrait
                    new_width = min_dimension
                    new_height = max(min_dimension, int(min_dimension / aspect_ratio))

            # Resize
            resized_image = image.resize((new_width, new_height))

            # Save the resized image at 60% quality
            resized_image.save(self.thumbnail.path, quality=60)
            resized_image.close()

            super().save(*args, **kwargs)


class Contributor(models.Model):
    ID = models.UUIDField(
        primary_key=True, default=uuid.uuid4, verbose_name="Contributor ID"
    )

    # Populated via Google SO / admin panel
    name = models.CharField(max_length=200)
    email = models.EmailField()

    active = models.BooleanField(default=True, verbose_name="Active?")

    # Set automatically
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    # Implements email level banning
    banned = models.BooleanField(default=False, verbose_name="Banned?")
    ban_reason = models.TextField(blank=True, verbose_name="Ban Reason")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Contributors"

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"""
                Contributor(
                    {self.ID},
                    {self.name},
                    {self.email},
                    {self.created_at},
                    {self.updated_at},
                    {self.banned},
                    {self.ban_reason}
                )
                """


class Contribution(models.Model):
    ID = models.UUIDField(
        primary_key=True, default=uuid.uuid4, verbose_name="Contribution ID"
    )
    mesh = models.ForeignKey(
        Mesh,
        on_delete=models.CASCADE,
        verbose_name="Mesh ID",
        related_name="contributions",
    )
    contributor = models.ForeignKey(
        Contributor,
        on_delete=models.CASCADE,
        verbose_name="Contributor ID",
        related_name="contributions",
    )
    contributed_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Contribution Timestamp"
    )
    processed = models.BooleanField(default=False, verbose_name="Processed by ImageOps")
    processed_at = models.DateTimeField(
        blank=True, null=True, verbose_name="Processed Timestamp"
    )

    class Meta:
        ordering = ["-contributed_at"]
        verbose_name_plural = "Contributions"

    def __str__(self):
        return f"{self.ID}"

    def __repr__(self):
        return f"""
                Contribution(
                    {self.ID},
                    {self.mesh},
                    {self.contributor},
                    {self.contributed_at},
                    {self.processed},
                    {self.processed_at}
                )
                """


def set_image(obj, filename):
    upload_to = f"models/{obj.contribution.mesh.ID}/images"
    filename = f"{str(obj.ID)}.{filename.split('.')[-1].lower()}"

    return os.path.join(upload_to, filename)


class Image(models.Model):
    ID = models.UUIDField(primary_key=True, default=uuid.uuid4, verbose_name="Image ID")
    contribution = models.ForeignKey(
        Contribution, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=set_image, blank=False, max_length=255)
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    # Multiple choices for label - Also incorporates general image quality.
    label_options = [("nsfw", "NSFW"), ("good", "Good"), ("bad", "Bad")]
    label = models.CharField(max_length=50, blank=True, choices=label_options)
    remark = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Images"

    def __str__(self):
        return f"{self.ID}"

    def __repr__(self):
        return f"""
                Image(
                    {self.ID},
                    {self.contribution},
                    {self.image.url},
                    {self.label},
                    {self.remark}
                )
                """


class ARK(models.Model):
    """
    ARK model for storing ARKs for each run.

    """

    ark = models.CharField(primary_key=True, max_length=200)

    # ARK components
    naan = models.CharField(max_length=10, blank=False, verbose_name="NAAN")
    shoulder = models.CharField(
        max_length=10, blank=False, verbose_name="NAAN Shoulder"
    )
    assigned_name = models.CharField(
        max_length=100, blank=False, verbose_name="Assigned Name"
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    # Bound content - blank=False forces us to maintain metadata
    url = models.URLField(
        blank=False, verbose_name="Bound URL"
    )  # NOTE: This is the URL of the bound content (.glb)
    metadata = models.JSONField(
        blank=False, verbose_name="Metadata"
    )  # CHECK: if this can be used as API meanwhile FIXME: LATE_EXP:
    def_commit = (
        "This ARK was generated & is managed by Project Tirtha (https://tirtha.niser.ac.in). "
        + "We are committed to maintaining this ARK as per our Terms of Use (https://tirtha.niser.ac.in/#terms) "
        + "and Privacy Policy (https://tirtha.niser.ac.in/#privacy)."
    )
    commitment = models.TextField(
        default=def_commit.strip(), blank=False, verbose_name="Commitment"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "ARKs"

    def __str__(self):
        return f"ark:/{self.ark}"

    def save(self, *args, **kwargs):
        if not self.shoulder.startswith("/"):
            raise ValueError(f"Shoulder {self.shoulder} must start with a /.")

        expected_ark = f"{self.naan}{self.shoulder}{self.assigned_name}"
        if self.ark != expected_ark:
            raise ValueError(f"Expected {expected_ark}. Got {self.ark}.")
        super().save(*args, **kwargs)


class Run(models.Model):
    ID = ShortUUIDField(
        primary_key=True, length=16, max_length=16, verbose_name="Run ID"
    )
    mesh = models.ForeignKey(
        Mesh, on_delete=models.CASCADE, verbose_name="Mesh ID", related_name="runs"
    )
    ark = models.OneToOneField(
        ARK,
        on_delete=models.DO_NOTHING,  # NOTE: DO NOT DELETE SUCCESSFUL RUNS - THIS VIOLATES THE ARK SPEC
        verbose_name="ARK",
        related_name="run",
        blank=True,
        null=True,
    )

    started_at = models.DateTimeField("Start timestamp", auto_now_add=True)
    ended_at = models.DateTimeField("End timestamp", blank=True, null=True)
    directory = models.CharField(
        max_length=200, blank=True, verbose_name="Run directory"
    )

    # Status of the run
    status_options = [
        ("Processing", "Processing"),
        ("Error", "Error"),
        ("Archived", "Archived"),
    ]
    status = models.CharField(
        max_length=50, blank=False, choices=status_options, default="Processing"
    )

    # Metadata
    contributors = models.ManyToManyField(
        Contributor, verbose_name="Contributors", related_name="runs"
    )
    images = models.ManyToManyField(Image, verbose_name="Images", related_name="runs")

    # Rotation and minimum observation angle for <model-viewer>
    rotaX = models.IntegerField(
        default=0, null=True, verbose_name="Rotation about X-axis"
    )
    rotaY = models.IntegerField(
        default=0, null=True, verbose_name="Rotation about Y-axis"
    )
    rotaZ = models.IntegerField(
        default=0, null=True, verbose_name="Rotation about Z-axis"
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name_plural = "Runs"

    def __str__(self):
        return f"{self.ID}"

    def __repr__(self):
        return f"""
                Run(
                    {self.ID},
                    {self.mesh},
                    {self.started_at},
                    {self.ended_at},
                    {self.directory},
                    {self.status},
                    {self.ark.url}
                )
                """

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.directory:
            self.directory = f"{self.mesh.ID}/cache/{self.started_at.strftime('%Y-%m-%d-%H-%M-%S')}__{str(self.ID)}"
        super().save(update_fields=["directory"])
